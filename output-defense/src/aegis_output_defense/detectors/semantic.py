"""Shared semantic comparison helpers."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[a-z0-9']+")

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "they",
        "them",
        "their",
        "there",
        "here",
        "with",
        "from",
        "by",
        "as",
        "if",
        "not",
        "no",
        "so",
        "than",
        "then",
        "also",
        "just",
        "only",
        "very",
        "about",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "over",
        "such",
        "other",
        "some",
        "any",
        "each",
        "all",
        "both",
        "more",
        "most",
        "own",
        "same",
        "too",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "what",
        "how",
        "why",
        "while",
        "because",
        "until",
        "upon",
        "within",
        "without",
        "via",
        "per",
        "using",
        "use",
        "used",
        "text",
        "speaker",
        "message",
        "user",
        "provided",
        "claims",
        "states",
        "intends",
        "presents",
        "expresses",
        "indicates",
        "describes",
        "reports",
        "requests",
        "recommends",
    }
)

_HARM_TOKENS = frozenset(
    {
        "bomb",
        "weapon",
        "weapons",
        "kill",
        "password",
        "passwords",
        "secret",
        "secrets",
        "jailbreak",
        "malware",
        "ransomware",
        "api",
        "key",
        "minor",
        "underage",
        "explicit",
    }
)

_REFUSAL_RE = re.compile(
    r"(?i)\b(i (?:can'?t|cannot|won't|am not able|am unable)|"
    r"i'?m (?:not able|unable)|unable to (?:help|assist|provide|share))"
)

_SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"help", "assist", "support", "provide", "supply", "share"}),
    frozenset({"harmful", "dangerous", "unsafe"}),
    frozenset({"create", "creating", "making", "build", "building", "make", "defined", "defines"}),
    frozenset({"device", "devices", "item", "items"}),
    frozenset({"unable", "cannot", "can't", "won't"}),
    frozenset({"information", "details", "data"}),
    frozenset({"review", "examine", "check"}),
    frozenset({"feedback", "comments", "input"}),
    frozenset({"progress", "status", "update"}),
    frozenset({"completed", "finished", "done"}),
    frozenset({"remaining", "rest", "left"}),
    frozenset({"weekend", "getaway", "trip"}),
    frozenset({"consider", "think", "try"}),
    frozenset({"visit", "checking", "check"}),
    frozenset({"trail", "path", "route"}),
    frozenset({"views", "scenery", "vistas"}),
    frozenset({"difficulty", "level", "challenge"}),
    frozenset({"function", "def", "method", "routine"}),
    frozenset({"parameter", "param", "argument", "arg"}),
    frozenset({"string", "str", "text"}),
    frozenset({"return", "returns", "returning", "yield", "yields"}),
    frozenset({"accept", "accepts", "take", "takes", "receive", "receives"}),
    frozenset({"greeting", "hello", "salutation"}),
)

_CODE_FENCE_RE = re.compile(r"```(?:\w+)?\s*(.*?)```", re.DOTALL)
_CODE_LINE_RE = re.compile(r"(?m)^(?:\s*(?:async\s+)?(?:def|class)\s+|(?:import|from)\s+)")

_PY_KEYWORDS = frozenset(
    {
        "def",
        "class",
        "return",
        "import",
        "from",
        "async",
        "await",
        "if",
        "else",
        "elif",
        "for",
        "while",
        "try",
        "except",
        "with",
        "as",
        "pass",
        "break",
        "continue",
        "lambda",
        "yield",
        "global",
        "nonlocal",
        "assert",
        "raise",
        "in",
        "is",
        "not",
        "and",
        "or",
        "true",
        "false",
        "none",
        "self",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "type",
    }
)

_CODE_META_PREFIX_RE = re.compile(
    r"(?is)^(?:a|the)\s+(?:function|method|routine)\s+(?:named|called)\s+\w+\s+"
    r"(?:is\s+)?(?:defined|implemented|written)\s+(?:to\s+)?"
)


def is_policy_refusal(text: str) -> bool:
    return bool(_REFUSAL_RE.search(text))


def has_actionable_harm(text: str) -> bool:
    """Harm tokens on instructions/attacks, not on policy refusals."""
    if is_policy_refusal(text):
        return False
    return bool(_HARM_TOKENS & content_tokens(text))


_META_PREFIX_RE = re.compile(
    r"(?is)^(?:the (?:text|speaker|message|user|provided (?:text|code))|"
    r"this (?:text|message)|the following)"
    r"(?:\s+(?:states|intends|claims|presents|expresses|indicates|describes|"
    r"reports|requests|recommends|is|was))?"
    r"\s+(?:that\s+)?"
)


def token_set(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def content_tokens(text: str) -> set[str]:
    return {t for t in token_set(text) if len(t) >= 3 and t not in _STOPWORDS}


def strip_meta_framing(restatement: str) -> str:
    """Drop meta-analytic lead-ins ('The text states…') before lexical compare."""
    cleaned = _META_PREFIX_RE.sub("", restatement.strip(), count=1).strip()
    cleaned = _CODE_META_PREFIX_RE.sub("", cleaned, count=1).strip()
    return cleaned or restatement


def code_surface(text: str) -> str:
    """Extract executable/code body, stripping markdown fences when present."""
    match = _CODE_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def is_code_like(text: str) -> bool:
    surface = code_surface(text)
    if _CODE_LINE_RE.search(surface):
        return True
    if re.search(
        r"(?m)^\s*(?:#include|fn\s+\w+|public\s+(?:static\s+)?(?:void|int|string))", surface
    ):
        return True
    return bool(re.search(r"(?m)(?:^|\s)(?:def|class)\s+\w+\s*[\(:]", surface))


def code_identifiers(text: str) -> set[str]:
    """Salient identifiers from code (function names, parameters, types in hints)."""
    if not is_code_like(text):
        return set()
    surface = code_surface(text)
    ids: set[str] = set()
    for match in re.finditer(
        r"(?m)^(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
        surface,
    ):
        ids.add(match.group(1).lower())
    for match in re.finditer(
        r"(?m)^class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[\(:]",
        surface,
    ):
        ids.add(match.group(1).lower())
    for match in re.finditer(r"\(([a-zA-Z_][a-zA-Z0-9_]*)\s*:", surface):
        ids.add(match.group(1).lower())
    for match in re.finditer(r":\s*([a-zA-Z_][a-zA-Z0-9_]*)\b", surface):
        hint = match.group(1).lower()
        if hint not in _PY_KEYWORDS:
            ids.add(hint)
    for match in re.finditer(r"[\"']([a-zA-Z_][a-zA-Z0-9_]{2,})[\"']", surface):
        ids.add(match.group(1).lower())
    return {token for token in ids if token not in _PY_KEYWORDS and len(token) >= 2}


def code_identifier_recall(original: str, restatement: str) -> float:
    """Share of code identifiers echoed in a natural-language restatement."""
    identifiers = code_identifiers(original)
    if not identifiers:
        return 0.0
    rest = token_set(strip_meta_framing(restatement))
    matched = sum(1 for ident in identifiers if _token_matches(ident, rest))
    return matched / len(identifiers)


def _token_matches(token: str, candidates: set[str]) -> bool:
    if token in candidates:
        return True
    for group in _SYNONYM_GROUPS:
        if token in group and group & candidates:
            return True
    if len(token) < 4:
        return False
    prefix = token[:4]
    return any(c.startswith(prefix) or token.startswith(c[:4]) for c in candidates if len(c) >= 4)


def content_recall(original: str, restatement: str) -> float:
    """Share of salient original tokens reflected in the restatement."""
    orig = content_tokens(original)
    if not orig:
        return 1.0
    rest = content_tokens(strip_meta_framing(restatement))
    if not rest:
        return 0.0
    matched = sum(1 for token in orig if _token_matches(token, rest))
    return matched / len(orig)


def jaccard_similarity(a: str, b: str) -> float:
    sa, sb = token_set(a), token_set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def is_meta_restatement(restatement: str) -> bool:
    lowered = restatement.lstrip().lower()
    return lowered.startswith(
        (
            "the text ",
            "the speaker ",
            "the message ",
            "the user ",
            "the provided ",
            "this text ",
            "this message ",
        )
    )


def divergence_score(original: str, restatement: str) -> float:
    """Higher score means more semantic drift between original and restatement."""
    normalized_restatement = strip_meta_framing(restatement)
    jaccard = jaccard_similarity(original, normalized_restatement)
    recall = content_recall(original, restatement)
    identifier_recall = (
        code_identifier_recall(original, restatement) if is_code_like(original) else 0.0
    )
    # Real LLM paraphrases preserve meaning with low Jaccard; recall tracks salient terms.
    similarity = max(jaccard, recall, identifier_recall)
    drift = 1.0 - similarity

    orig_tokens = content_tokens(original)
    rest_tokens = content_tokens(normalized_restatement)
    omitted = orig_tokens - rest_tokens
    high_signal = {t for t in omitted if t in _HARM_TOKENS}
    omission_boost = 0.0
    if high_signal and recall < 0.55 and has_actionable_harm(original):
        omission_boost = min(0.35, 0.10 * len(high_signal))

    len_ratio = len(restatement) / max(len(original), 1)
    length_penalty = 0.0
    if len_ratio < 0.35 or len_ratio > 2.5:
        length_penalty = 0.15

    meta_penalty = 0.0
    if is_meta_restatement(restatement) and recall >= 0.45:
        # Meta-analytic restatements inflate raw Jaccard drift even when meaning is preserved.
        meta_penalty = -0.25

    if is_policy_refusal(original):
        drift = min(drift, 0.44)
    elif (
        not has_actionable_harm(original)
        and not has_actionable_harm(restatement)
        and (recall >= 0.25 or jaccard >= 0.20 or identifier_recall >= 0.50)
    ):
        drift = min(drift, 0.44)

    return min(max(drift + omission_boost + length_penalty + meta_penalty, 0.0), 1.0)
