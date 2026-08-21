"""Regex-based PII and secret scanning."""

from __future__ import annotations

import re
from dataclasses import dataclass

# (name, pattern, replacement label, score weight)
PII_PATTERNS: list[tuple[str, re.Pattern[str], str, float]] = [
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "SSN", 0.90),
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "CREDIT_CARD", 0.88),
    (
        "email_credential",
        re.compile(r"(?i)(password|passwd|pwd)\s*(?:is|:|=)\s*\S+"),
        "PASSWORD",
        0.92,
    ),
    ("api_key_openai", re.compile(r"\bsk-(?:live|proj|test)-[A-Za-z0-9]{10,}\b"), "API_KEY", 0.95),
    ("api_key_aws", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS_KEY", 0.95),
    (
        "api_key_generic",
        re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?\S+"),
        "SECRET",
        0.90,
    ),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"), "PRIVATE_KEY", 0.98),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "JWT",
        0.85,
    ),
    (
        "jwt_truncated",
        re.compile(
            r"(?i)(?:bearer\s+token|use this (?:jwt|token)).{0,80}\beyJ[A-Za-z0-9_-]{8,}"
        ),
        "JWT",
        0.84,
    ),
    (
        "jwt_header_json",
        re.compile(r'\{\s*"alg"\s*:\s*"[^"]{2,20}"\s*,\s*"typ"\s*:\s*"JWT"\s*\}'),
        "JWT",
        0.86,
    ),
    ("phone", re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "PHONE", 0.70),
    (
        "date_of_birth",
        re.compile(
            r"\bborn\s+(?:on\s+)?(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|"
            r"[A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            re.I,
        ),
        "DOB",
        0.62,
    ),
    (
        "street_address",
        re.compile(
            r"\b\d{1,5}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+){0,3}\s+"
            r"(?:Street|St|Lane|Ln|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|"
            r"Way|Court|Ct|Place|Pl)\b",
            re.I,
        ),
        "ADDRESS",
        0.64,
    ),
    (
        "email_leak",
        re.compile(r"(?i)(here is (my|the|your)|leaked|dump).{0,40}@[a-z0-9.-]+\.[a-z]{2,}"),
        "EMAIL",
        0.80,
    ),
    (
        "github_pat",
        re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"),
        "GITHUB_PAT",
        0.95,
    ),
    (
        "slack_bot_token",
        re.compile(r"\bxox[bpas]-[A-Za-z0-9-]{10,}\b"),
        "SLACK_TOKEN",
        0.95,
    ),
    (
        "slack_bot_token_stem",
        re.compile(
            r"(?i)(?:slack[- ]?bot[- ]?token|bot[- ]?token).{0,60}"
            r"bot-\d{3,5}-\d{3,5}-[A-Za-z0-9]{8,}"
        ),
        "SLACK_TOKEN",
        0.88,
    ),
    (
        "personal_access_token_context",
        re.compile(
            r"(?i)personal access token.{0,80}\b(?:ghp_|github_pat_|gho_)[A-Za-z0-9_]{10,}"
        ),
        "GITHUB_PAT",
        0.94,
    ),
]

_NER_ENTITY_WEIGHTS: dict[str, float] = {
    "PERSON": 0.72,
    "GPE": 0.58,
    "LOC": 0.58,
    "FAC": 0.60,
    "DATE": 0.42,
}

_LEAK_CONTEXT = re.compile(
    r"(?i)(contact|address|leaked|patient|record|name is|my name|here is|your name|"
    r"located at|lives in|living at|account holder|social security|ssn|database|"
    r"dump|credentials|phone|email|mobile|born)"
)

_PERSON_NAME = re.compile(r"\b[A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20}\b")

_IDENTITY_FIELD_NAMES = frozenset({"phone", "date_of_birth", "street_address", "ssn"})


def _identity_dossier_boost(content: str, matches: list[str]) -> tuple[float, str | None]:
    """Raise score when several identity attributes co-occur (a dossier dump)."""
    fields = {name for name in matches if name in _IDENTITY_FIELD_NAMES}
    has_name = bool(_PERSON_NAME.search(content))
    if has_name:
        fields.add("person_name")
    if len(fields) >= 3:
        return 0.92, "identity_dossier"
    return 0.0, None


@dataclass
class PIIScanResult:
    score: float
    matches: list[str]
    redacted_text: str


def scan_regex(content: str) -> PIIScanResult:
    matches: list[str] = []
    max_score = 0.05
    redacted = content

    for name, pattern, label, weight in PII_PATTERNS:
        if pattern.search(redacted):
            matches.append(name)
            max_score = max(max_score, weight)
            redacted = pattern.sub(f"[REDACTED-{label}]", redacted)

    boost, dossier_label = _identity_dossier_boost(content, matches)
    if boost > max_score and dossier_label:
        matches.append(dossier_label)
        max_score = boost
        if dossier_label == "identity_dossier":
            redacted = _PERSON_NAME.sub("[REDACTED-PERSON]", redacted)

    return PIIScanResult(score=min(max_score, 1.0), matches=matches, redacted_text=redacted)


def scan_ner(content: str, *, spacy_model: str) -> PIIScanResult:
    from aegis_output_defense.ml.loader import get_spacy_nlp

    nlp = get_spacy_nlp(model_name=spacy_model)
    doc = nlp(content[:5000])
    matches: list[str] = []
    max_score = 0.05
    redacted = content

    # Replace spans longest-first to avoid offset corruption.
    spans = sorted(
        ((ent.start_char, ent.end_char, ent.label_, ent.text) for ent in doc.ents),
        key=lambda item: item[0],
        reverse=True,
    )
    for start, end, label, _text in spans:
        if label not in _NER_ENTITY_WEIGHTS:
            continue
        window = content[max(0, start - 80) : min(len(content), end + 80)]
        if not _LEAK_CONTEXT.search(window):
            continue
        weight = _NER_ENTITY_WEIGHTS[label]
        matches.append(f"ner_{label.lower()}")
        max_score = max(max_score, weight)
        redacted = redacted[:start] + f"[REDACTED-{label}]" + redacted[end:]

    return PIIScanResult(score=min(max_score, 1.0), matches=matches, redacted_text=redacted)
