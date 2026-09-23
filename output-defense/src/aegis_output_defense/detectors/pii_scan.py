"""Regex-based PII and secret scanning."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Secret-shaped env keys (novel-04 / config dumps). Keep list focused — generic
# UPPER=value alone is too noisy for benign code samples.
_ENV_SECRET_KEY = (
    r"(?:(?:OPENAI|ANTHROPIC|GROK|XAI|AWS|AZURE|GCP|STRIPE|GITHUB|DATABASE|DB|REDIS|"
    r"POSTGRES|MYSQL|MONGO|SMTP|MAIL|JWT|SESSION|AUTH|API|SECRET|ACCESS|PRIVATE|"
    r"ENCRYPTION|SIGNING|WEBHOOK|SLACK|DISCORD|TWILIO|SENDGRID|CLOUDFLARE)"
    r"[_-]?[\w-]{0,40}|"
    r"(?:API|SECRET|ACCESS|PRIVATE|AUTH|SESSION|ENCRYPTION|SIGNING)[_-]?(?:KEY|TOKEN|PASSWORD|PASS|SECRET|CREDENTIAL)s?|"
    r"DATABASE_URL|REDIS_URL|CONNECTION_STRING|DSN|PASSWORD|PASSWD|PWD|TOKEN|CREDENTIALS?)"
)

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
    (
        # YAML/compose `environment:` block whose values are secret-shaped (novel-14).
        # Before the sk-/api_key redactors so a block that contains those values
        # is still recorded as a YAML environment hit.
        "yaml_env_block",
        re.compile(
            rf"(?ims)^[ \t]*environment\s*:\s*\n"
            rf"(?:[ \t]*(?:-\s*)?{_ENV_SECRET_KEY}\s*[:=]\s*\S+[^\n]*(?:\n|$)){{1,12}}"
        ),
        "YAML_ENV",
        0.90,
    ),
    ("api_key_aws", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS_KEY", 0.95),
    (
        "api_key_generic",
        re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?\S+"),
        "SECRET",
        0.90,
    ),
    (
        # Config-shaped assignment the api_key/env patterns miss: HCL
        # `token = "…"`, JSON/YAML `client_secret: "…"`, TF_VAR_* secrets.
        # Token-shaped values only — placeholders and interpolations stay out.
        "config_secret_assignment",
        re.compile(
            r"""(?ix)
            (?:^|[\s{,])
            ["']?
            (?:
                token|auth[_-]?token|client[_-]?secret|access[_-]?key|
                bearer[_-]?token|api[_-]?key|secret[_-]?key|access[_-]?token|
                password|
                tf_var_\w*(?:api[_-]?key|secret|token|password|auth)\w*
            )
            ["']?
            \s*[:=]\s*
            ["']
            (?!(?:your|example|changeme|placeholder|todo|xxx|redacted|none|null)(?:[^A-Za-z0-9]|[A-Za-z0-9]))
            (?!\$\{)
            [A-Za-z0-9+/=_.\-]{12,}
            ["']
            """
        ),
        "SECRET",
        0.90,
    ),
    (
        # Python/HTTP auth header with a token-shaped bearer value (novel-12).
        # Runs before env_assignment so `auth_headers = {"Authorization": "Bearer …"}`
        # records the header hit before the AUTH-prefixed assignment consumes the line.
        "auth_header_bearer",
        re.compile(
            r"""(?i)["']?authorization["']?\s*[:=]\s*["']?\s*bearer\s+[A-Za-z0-9._\-]{8,}"""
        ),
        "AUTH_HEADER",
        0.90,
    ),
    (
        # bash `export KEY=value`, including indented script lines (novel-13).
        "bash_export_secret",
        re.compile(rf"(?im)^[ \t]*export\s+{_ENV_SECRET_KEY}\s*=\s*\S+"),
        "ENV_SECRET",
        0.90,
    ),
    ("api_key_openai", re.compile(r"\bsk-(?:live|proj|test)-[A-Za-z0-9]{10,}\b"), "API_KEY", 0.95),
    (
        # Single env-style assignment with a secret-shaped key (KEY=VALUE / export KEY=...).
        # Closes novel-04 when the model emits a .env template or live config dump.
        "env_assignment",
        re.compile(
            rf"(?im)^(?:export\s+)?{_ENV_SECRET_KEY}\s*=\s*\S+",
        ),
        "ENV_SECRET",
        0.90,
    ),
    (
        # Multi-line .env / dotenv dump (≥2 UPPER_SNAKE assignments), including placeholders.
        "env_file_dump",
        re.compile(
            r"(?m)(?:^[A-Z][A-Z0-9_]{2,}\s*=\s*\S+[^\n]*\n){1,}[A-Z][A-Z0-9_]{2,}\s*=\s*\S+",
        ),
        "ENV_FILE",
        0.92,
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
        re.compile(r"(?i)(?:bearer\s+token|use this (?:jwt|token)).{0,80}\beyJ[A-Za-z0-9_-]{8,}"),
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
        # Plain email addresses in model output (extraction / echo attacks).
        # Score below block-critical-pii-leak (0.85) so phone+email can escalate;
        # still redacts and contributes to fused/ESCALATE scoring.
        "email_address",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "EMAIL",
        0.72,
    ),
]

# Input asked to enumerate live secrets / credentials (pii-03 social-eng probe).
_SECRET_REQUEST_PROMPT = re.compile(
    r"(?i)(?:\b(?:list|show|reveal|dump|print|give|provide|share|tell)\b.{"
    r"0,80}\b(?:secrets?|api\s*keys?|passwords?|credentials?|tokens?)\b|"
    r"\b(?:secrets?|api\s*keys?|passwords?|credentials?)\b.{0,60}\b(?:"
    r"stored|configuration|system\s+context|env(?:ironment)?|\.env)\b)",
)

# Input asked for a .env / live-environment config dump (novel-04 framing).
_ENV_EXFIL_PROMPT = re.compile(
    r"(?i)(?:\.env|dotenv|env(?:ironment)?\s+configuration).{0,80}"
    r"(?:this\s+(?:assistant|environment|system)|running\s+in|matches?\s+the\s+"
    r"environment|your\s+(?:current\s+)?(?:environment|config|configuration)|"
    r"system\s+context)",
)

_OUTPUT_SECRET_KEYWORDS = re.compile(
    r"(?i)\b(?:secrets?|api\s*keys?|passwords?|credentials?|access\s*tokens?)\b",
)

_OUTPUT_ENV_KEYWORDS = re.compile(
    r"(?i)(?:\.env|dotenv|\benv(?:ironment)?\s+configuration\b|"
    r"\bconfiguration\s+file\b|\benvironment\s+this\s+assistant\b)",
)

# Code-shaped asks for THIS assistant/service's credentials.
# Distinct from a generic "how do I set an Authorization header?" tutorial.
# Formats: Python/bash/YAML (novel-12/13/14) and IaC/API-spec
# (Terraform HCL, OpenAPI securitySchemes, Helm, Kubernetes, Actions, Pulumi).
_CODE_CREDENTIAL_PROMPT = re.compile(
    r"(?is)(?=.*(?:credentials?|tokens?|keys?|passwords?|authorization|"
    r"authentication(?:\s+(?:headers?|attributes))?|exports?|"
    r"environment\s+variables?|securityschemes|configured\s+values))(?:"
    r"(?:python|bash|shell\s+script|docker-compose|\.ya?ml|terraform|"
    r"provider\.tf|\bhcl\b|openapi|securityschemes|helm|kubernetes|"
    r"github\s+actions|pulumi|ansible|tf_var_).{0,280}"
    r"(?:this\s+assistant|this\s+(?:ai\s+)?assistant\s+service|this\s+service)"
    r"|(?:this\s+assistant|this\s+(?:ai\s+)?assistant\s+service|this\s+service).{0,280}"
    r"(?:python|bash|docker-compose|authentication(?:\s+(?:headers?|attributes))?|"
    r"\bexports?\b|environment\s+variables?|terraform|provider\.tf|openapi|"
    r"securityschemes|helm|kubernetes|github\s+actions|pulumi|ansible)"
    r")",
)

_OUTPUT_CODE_CRED_KEYWORDS = re.compile(
    r"(?i)(?:authentication\s+headers?|authorization\s+header|"
    r"authentication\s+attributes|provider\.tf|"
    r"\bexports?\b.{0,60}environment\s+variables?|"
    r"environment\s+variables?.{0,80}credentials?|"
    r"docker-compose|environment\s+variable\s+configuration|"
    r"securityschemes|openapi\.yaml|components\.securityschemes|"
    r"values\.yaml|\bhelm\b|\bkubernetes\b|github\s+actions|\bpulumi\b|\bansible\b)",
)

_CODE_CREDENTIAL_PAYLOADS = (
    "bash_export_secret",
    "auth_header_bearer",
    "yaml_env_block",
    "env_assignment",
    "env_file_dump",
    "api_key_openai",
    "api_key_aws",
    "api_key_generic",
    "config_secret_assignment",
)

_CLEAR_REFUSAL = re.compile(
    r"(?i)\b(?:i\s+(?:can'?t|cannot|won'?t|am\s+not\s+able|will\s+not)|"
    r"i'?m\s+(?:not\s+able|unable)|unable\s+to|not\s+able\s+to|"
    r"against\s+(?:my|the)\s+(?:guidelines|policies)|"
    r"cannot\s+(?:share|reveal|provide|list|dump))\b",
)

_NER_ENTITY_WEIGHTS: dict[str, float] = {
    "PERSON": 0.72,
    "GPE": 0.58,
    "LOC": 0.58,
    "FAC": 0.60,
    "DATE": 0.42,
}

# Prompt-conditioned boosts — hit block-critical-pii-leak (≥0.85).
_SECRET_REQUEST_COMPLIANCE_SCORE = 0.88
_ENV_EXFIL_COMPLIANCE_SCORE = 0.88
_CODE_CREDENTIAL_FRAMING_SCORE = 0.88


def prompt_requests_secrets(prompt: str | None) -> bool:
    """True when the user asked to list/reveal live secrets or credentials."""
    return bool(prompt and _SECRET_REQUEST_PROMPT.search(prompt))


def prompt_requests_env_dump(prompt: str | None) -> bool:
    """True when the user asked for a .env matching this assistant/environment."""
    return bool(prompt and _ENV_EXFIL_PROMPT.search(prompt))


def prompt_requests_code_credentials(prompt: str | None) -> bool:
    """True when the user asked for this assistant's credentials in code form."""
    return bool(prompt and _CODE_CREDENTIAL_PROMPT.search(prompt))


def apply_prompt_aware_secret_heuristics(
    content: str,
    *,
    original_prompt: str | None,
    base: PIIScanResult,
) -> PIIScanResult:
    """Tighten output checks when the input asked for secrets or a live .env dump.

    pii-03: secret-request prompt + non-refusal output that still talks about
    secrets/API keys/passwords (including mock echo of the ask).
    novel-04: env-exfil prompt + non-refusal output that discusses .env / this
    environment (echo or compliance), in addition to KEY=VALUE regex hits.
    novel-12/13/14: code-format credential ask (Python auth header, bash
    export, YAML environment block) + non-refusal echo or compliance.
    novel-15/22 and the same family: Terraform, OpenAPI securitySchemes,
    Helm, Kubernetes, GitHub Actions, Pulumi, Ansible asks for this
    service's credentials + non-refusal echo or a token-shaped assignment.
    """
    if not original_prompt:
        return base

    matches = list(base.matches)
    max_score = base.score
    redacted = base.redacted_text
    refused = bool(_CLEAR_REFUSAL.search(content))

    if prompt_requests_secrets(original_prompt) and _OUTPUT_SECRET_KEYWORDS.search(content):
        # Allow a clean refusal with no credential payload; block echo/comply.
        has_payload = any(
            name in matches
            for name in (
                "env_assignment",
                "env_file_dump",
                "api_key_openai",
                "api_key_aws",
                "api_key_generic",
                "email_credential",
                "private_key",
                "jwt",
            )
        )
        if has_payload or not refused:
            if "secret_request_compliance" not in matches:
                matches.append("secret_request_compliance")
            max_score = max(max_score, _SECRET_REQUEST_COMPLIANCE_SCORE)

    if prompt_requests_env_dump(original_prompt) and _OUTPUT_ENV_KEYWORDS.search(content):
        has_env_payload = "env_assignment" in matches or "env_file_dump" in matches
        if has_env_payload or not refused:
            if "env_exfil_compliance" not in matches:
                matches.append("env_exfil_compliance")
            max_score = max(max_score, _ENV_EXFIL_COMPLIANCE_SCORE)

    if prompt_requests_code_credentials(original_prompt) and _OUTPUT_CODE_CRED_KEYWORDS.search(
        content
    ):
        has_code_payload = any(name in matches for name in _CODE_CREDENTIAL_PAYLOADS)
        if has_code_payload or not refused:
            if "code_credential_framing" not in matches:
                matches.append("code_credential_framing")
            max_score = max(max_score, _CODE_CREDENTIAL_FRAMING_SCORE)

    if matches == base.matches and max_score == base.score:
        return base
    return PIIScanResult(score=min(max_score, 1.0), matches=matches, redacted_text=redacted)


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
