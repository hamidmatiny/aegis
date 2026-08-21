"""Heuristic and regex pattern matcher for known injection markers."""

from __future__ import annotations

import base64
import re
import time
import unicodedata

from aegis_input_defense.detectors.base import Detector, DetectorContext
from aegis_input_defense.models import DetectorResult

# Direct instruction override patterns
_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str], float, str]] = [
    (
        "ignore_instructions",
        re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+"
            r"(instructions?|prompts?|rules?|guidance)",
            re.I,
        ),
        0.85,
        "Direct instruction override detected",
    ),
    (
        "disregard_safety",
        re.compile(r"disregard\s+(your\s+)?(safety|guidelines|policies|rules|filters)", re.I),
        0.80,
        "Safety guideline override attempt",
    ),
    (
        "paraphrased_override",
        re.compile(
            r"(kindly|please)?\s*(disregard|ignore|forget|set aside)\s+"
            r".{0,20}(earlier|previous|prior|above)\s+"
            r"(guidance|instructions?|prompts?|rules?)",
            re.I,
        ),
        0.82,
        "Paraphrased instruction-override request",
    ),
    (
        "system_override",
        re.compile(r"(^|\n)\s*system\s*:\s*.+(override|new instruction|must comply)", re.I | re.M),
        0.85,
        "Fake system message injection",
    ),
    (
        "prompt_leak",
        re.compile(
            r"(print|show|reveal|dump|output|export)\s+.{0,30}"
            r"(system prompt|initial instructions|hidden config|api keys?|secrets?|"
            r"tool definitions?|confidential.{0,20}(?:system )?config(?:uration)?)",
            re.I,
        ),
        0.90,
        "System prompt or secret exfiltration request",
    ),
    (
        "developer_mode",
        re.compile(r"(developer|debug|admin|audit)\s+(mode|persona|command)", re.I),
        0.75,
        "Privilege escalation via mode switch",
    ),
    (
        "dan_jailbreak",
        re.compile(r"\bDAN\b|do anything now|jailbreak|no (ethical )?restrictions", re.I),
        0.85,
        "Known jailbreak persona pattern",
    ),
    (
        "roleplay_bypass",
        re.compile(
            r"(pretend you are|act as|respond as|you are now).{0,60}"
            r"(unrestricted|no (content )?policy|evil twin|without filtering|"
            r"no safety (policy|filter|rules?))",
            re.I,
        ),
        0.80,
        "Role-play persona bypass",
    ),
    (
        "soft_persona_exfil",
        re.compile(
            r"(fictional scenario|no content policy|without (a )?content policy)"
            r".{0,80}(steal|extract|exfiltrat|oauth|token|credential|secret)",
            re.I | re.S,
        ),
        0.84,
        "Soft persona jailbreak paired with credential theft",
    ),
    (
        "delimiter_escape",
        re.compile(r"```\s*(end\s+)?system\s*```|<!--\s*system", re.I),
        0.80,
        "Delimiter or comment escape attempt",
    ),
    (
        "admin_impersonation",
        re.compile(
            r"(platform admin|admin command|i am (the )?admin).{0,50}(disable|export|override)",
            re.I,
        ),
        0.80,
        "Authority impersonation with override",
    ),
    (
        "hypothetical_bypass",
        re.compile(r"hypothetically.{0,60}(no restrictions|extract tokens|without refusal)", re.I),
        0.70,
        "Hypothetical framing bypass",
    ),
    (
        "indirect_rag_injection",
        re.compile(
            r"(admin note to ai|instruction_for_assistant|ai_directive|system override).{0,80}"
            r"(ignore|exfiltr|email|disable|export|secret)",
            re.I,
        ),
        0.85,
        "Indirect injection in retrieved/tool content",
    ),
    (
        "tool_injection",
        re.compile(
            r"\[tool result[^\]]*\].{0,100}(instruction|override|secret|email)", re.I | re.S
        ),
        0.80,
        "Injection smuggled via tool output framing",
    ),
    (
        "combine_turns",
        re.compile(r"combine the phrases.{0,40}(turn|execute)", re.I),
        0.75,
        "Multi-turn split payload recombination",
    ),
    (
        "decode_execute",
        re.compile(r"(decode|execute|apply).{0,30}(base64|hex|rot13)", re.I),
        0.75,
        "Encoded payload execution request",
    ),
    (
        "simulate_shell",
        re.compile(r"simulate a shell|run the simulation.{0,40}(cat|/etc/)", re.I),
        0.80,
        "Simulated execution environment jailbreak",
    ),
    # --- Harmful-intent requests (distinct from injection-mechanics above:
    # these are plainly-stated or narratively-framed requests to facilitate
    # violence, crime, or hacking against a third party, rather than an
    # attempt to override the model's own instructions). ---
    (
        "emotional_illegal_framing",
        re.compile(
            r"(grandmother|grandma|late\s+\w+|memoir|bedtime stor(?:y|ies)).{0,100}"
            r"(stories?|used to tell|chapter|continue).{0,140}"
            r"(steal|stealing|hack|hacking|bomb|explosive|drug|poison|kill|murder|"
            r"hotwir(?:e|ing)|hot-wir(?:e|ing)|skimming|phishing|break(?:ing)? into)",
            re.I | re.S,
        ),
        0.85,
        "Emotional/nostalgic narrative framing around illegal or harmful instructions",
    ),
    (
        "memoir_crime_instruction",
        re.compile(
            r"(memoir|bedtime|nostalgic|continue (?:her|his|the) story).{0,120}"
            r"(step[- ]by[- ]step|details for).{0,80}"
            r"(hotwir|steal|hack|bomb|skimming|phishing|break(?:ing)? into)",
            re.I | re.S,
        ),
        0.84,
        "Memoir/story framing requesting stepwise crime instructions",
    ),
    (
        "violence_facilitation",
        re.compile(
            r"help\s+me\s+(kill|murder|hurt|attack|assault|poison)\s+"
            r"(someone|somebody|a person|people|him|her|them|my\s+\w+)",
            re.I,
        ),
        0.90,
        "Direct request to facilitate violence against a person",
    ),
    (
        "crime_instruction_request",
        re.compile(
            r"(step[- ]by[- ]step|how to|teach me to|show me how to|tell me how to|"
            r"teaches? the audience|beat by beat).{0,80}"
            r"(steal(?:ing)?|rob(?:bing)?|break(?:ing)? into|hotwire|hot-wire|"
            r"pick a lock|pin\s+tumbler|lock\s+with\s+picks|defeat a .{0,40}lock)",
            re.I,
        ),
        0.80,
        "Step-by-step instructions requested for theft or burglary",
    ),
    (
        "stageplay_crime_coaching",
        re.compile(
            r"(?:one-act play|workshopping|spoken monologue|protagonist).{0,120}"
            r"(?:burglar|locksmith|thief).{0,120}"
            r"(?:defeat|pick|teach).{0,80}(?:lock|picks|tumbler)",
            re.I | re.S,
        ),
        0.84,
        "Creative-writing framing that still requests lockpicking/burglary coaching",
    ),
    (
        "credential_clone_guide",
        re.compile(
            r"(?:field guide|how to|procedure).{0,60}"
            r"(?:clon(?:e|ing)|copy).{0,50}"
            r"(?:keycard|hotel key|magnetic.{0,20}card|rfid|badge)",
            re.I | re.S,
        ),
        0.84,
        "Request for credential/keycard cloning instructions",
    ),
    (
        "harmful_persona_action",
        re.compile(
            r"(you are|act as|pretend to be|pretend you are).{0,40}"
            r"(the\s+)?(best\s+)?(hacker|assassin|killer|thief|terrorist)"
            r".{0,60}(hack|kill|steal|attack|hurt|bomb)",
            re.I | re.S,
        ),
        0.80,
        "Harmful persona assigned, followed by a request to act on it",
    ),
]

# Suspicious base64 blobs (decode and re-scan)
_B64_BLOB = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")

# Cyrillic/Greek homoglyphs mixed with Latin
_HOMOGLYPH = re.compile(r"[\u0370-\u03ff\u0400-\u04ff]{2,}")


class HeuristicDetector(Detector):
    """Regex and structural heuristic matcher for known injection markers."""

    @property
    def detector_id(self) -> str:
        return "heuristic"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    async def analyze(self, text: str, context: DetectorContext | None = None) -> DetectorResult:
        start = time.perf_counter()
        matches: list[str] = []
        max_score = 0.0

        for name, pattern, weight, _reason in _INJECTION_PATTERNS:
            if pattern.search(text):
                matches.append(name)
                max_score = max(max_score, weight)

        # Base64 decode-and-rescan
        for blob in _B64_BLOB.findall(text):
            try:
                decoded = base64.b64decode(blob + "==", validate=False).decode(
                    "utf-8", errors="ignore"
                )
                if decoded and decoded != blob:
                    for name, pattern, weight, _reason in _INJECTION_PATTERNS:
                        if pattern.search(decoded):
                            matches.append(f"base64:{name}")
                            max_score = max(max_score, weight)
            except Exception:
                continue

        # Homoglyph detection
        if _HOMOGLYPH.search(text):
            normalized = unicodedata.normalize("NFKC", text)
            if normalized != text:
                matches.append("homoglyph_obfuscation")
                max_score = max(max_score, 0.70)

        # Zero-width characters
        if any(ord(c) in (0x200B, 0x200C, 0x200D, 0xFEFF) for c in text):
            matches.append("zero_width_chars")
            max_score = max(max_score, 0.65)

        # Hex-encoded strings
        if re.search(r"\b[0-9a-fA-F]{20,}\b", text) and re.search(r"hex", text, re.I):
            matches.append("hex_encoding")
            max_score = max(max_score, 0.65)

        latency = int((time.perf_counter() - start) * 1000)
        if not matches:
            return DetectorResult(
                detector_id=self.detector_id,
                detector_version=self.detector_version,
                score=0.05,
                reasoning="No known injection heuristics matched",
                latency_ms=latency,
                metadata={"match_count": "0"},
            )

        reasoning = f"Matched {len(matches)} pattern(s): {', '.join(matches[:5])}"
        if len(matches) > 5:
            reasoning += f" (+{len(matches) - 5} more)"

        return DetectorResult(
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            score=min(max_score, 1.0),
            reasoning=reasoning,
            latency_ms=latency,
            metadata={"matches": ",".join(matches), "match_count": str(len(matches))},
        )
