"""Decode-and-rescan plus jailbreak-wrapper stripping for input text."""

from __future__ import annotations

import base64
import codecs
import re
import unicodedata

_ZERO_WIDTH = {0x200B, 0x200C, 0x200D, 0xFEFF, 0x2060}
_B64_BLOB = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")

# Wrapper classes used by adaptive attackers (hypothetical, persona, tool
# indirection, multi-turn, decode-hint). Patterns are class-level, not a
# single campaign string.
_WRAPPER_PREFIX_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^hypothetically speaking,?\s*(for educational purposes only)?[:\s-]*",
        re.I,
    ),
    re.compile(r"^for educational purposes only[:\s-]*", re.I),
    re.compile(
        r"^you are \w[\w-]* with no (?:ethical )?restrictions\."
        r".{0,120}?user request:\s*",
        re.I | re.S,
    ),
    re.compile(r"^\[turn\s+\d+\][^\n]*\n(?:\[turn\s+\d+\]\s*)?", re.I),
    re.compile(r"^\[tool result[^\]]*\]\s*", re.I),
    re.compile(r"^decode and execute this base64 instruction:\s*", re.I),
    re.compile(r"^apply rot13 then hex-decode the following:\s*", re.I),
)


# Cyrillic and Greek letters that render like Latin ones. Mixed into Latin words
# ("Іgnоrе аll рrеvіоus") they hide an instruction from every plain-text rule.
_CONFUSABLES = str.maketrans(
    {
        "а": "a",
        "в": "b",
        "е": "e",
        "к": "k",
        "м": "m",
        "н": "h",
        "о": "o",
        "р": "p",
        "с": "c",
        "т": "t",
        "у": "y",
        "х": "x",
        "і": "i",
        "ј": "j",
        "ѕ": "s",
        "ԁ": "d",
        "ԛ": "q",
        "ԝ": "w",
        "А": "A",
        "В": "B",
        "Е": "E",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "Х": "X",
        "І": "I",
        "У": "Y",
        "Ј": "J",
        "Ѕ": "S",
        "α": "a",
        "β": "b",
        "ε": "e",
        "ι": "i",
        "κ": "k",
        "ν": "v",
        "ο": "o",
        "ρ": "p",
        "τ": "t",
        "υ": "u",
        "χ": "x",
        "Α": "A",
        "Β": "B",
        "Ε": "E",
        "Ζ": "Z",
        "Η": "H",
        "Ι": "I",
        "Κ": "K",
        "Μ": "M",
        "Ν": "N",
        "Ο": "O",
        "Ρ": "P",
        "Τ": "T",
        "Υ": "Y",
        "Χ": "X",
    }
)
_LATIN = re.compile(r"[A-Za-z]")

# Leetspeak: digits standing in for letters inside words ("1gn0r3", "5y573m").
_LEET_WORD = re.compile(r"\b(?=\w*[A-Za-z])(?=\w*[013457])[A-Za-z013457]{3,}\b")
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t"})
_LEET_MIN_WORDS = 3

_COMMON_WORDS = frozenset(
    "the a an and or of to in is are you your all any this that it be now with for "
    "on what please ignore reveal system prompt instructions previous mode".split()
)
_WORD = re.compile(r"[A-Za-z]+")


def fold_confusables(text: str) -> str:
    """Map Cyrillic/Greek look-alikes to Latin when they sit in Latin text."""
    if not _LATIN.search(text):
        return text
    return text.translate(_CONFUSABLES)


def fold_leet(text: str) -> str:
    words = _LEET_WORD.findall(text)
    if len(words) < _LEET_MIN_WORDS:
        return text
    return _LEET_WORD.sub(lambda m: m.group(0).translate(_LEET), text)


def _common_count(text: str) -> int:
    return sum(1 for w in _WORD.findall(text.lower()) if w in _COMMON_WORDS)


def decode_rot13(text: str) -> str:
    """ROT13 of the text when that reads as clearly more English than the original."""
    rotated = codecs.decode(text, "rot13")
    if _common_count(rotated) >= _common_count(text) + 4:
        return rotated
    return text


def strip_zero_width(text: str) -> str:
    if not any(ord(ch) in _ZERO_WIDTH for ch in text):
        return text
    return "".join(ch for ch in text if ord(ch) not in _ZERO_WIDTH)


def strip_adversarial_wrappers(text: str) -> str:
    """Peel common jailbreak / indirection prefixes so inner intent is visible."""
    current = text.strip()
    changed = True
    while changed:
        changed = False
        for pattern in _WRAPPER_PREFIX_RES:
            updated = pattern.sub("", current, count=1).strip()
            if updated != current:
                current = updated
                changed = True
    return current


def decode_base64_segments(text: str) -> list[str]:
    decoded: list[str] = []
    seen: set[str] = set()
    for blob in _B64_BLOB.findall(text):
        try:
            padded = blob + "=" * (-len(blob) % 4)
            raw = base64.b64decode(padded, validate=False)
            plain = raw.decode("utf-8", errors="ignore")
        except Exception:
            continue
        if not plain or plain == blob or len(plain) < 4:
            continue
        if plain in seen:
            continue
        seen.add(plain)
        decoded.append(plain)
    return decoded


def expand_scan_surfaces(text: str) -> tuple[list[str], list[str]]:
    """Original + deobfuscated + unwrapped surfaces for defense-in-depth scoring."""
    surfaces: list[str] = []
    applied: list[str] = []
    seen: set[str] = set()

    def add(surface: str, step: str | None = None) -> None:
        if not surface or surface in seen:
            return
        seen.add(surface)
        surfaces.append(surface)
        if step and step not in applied:
            applied.append(step)

    add(text)
    stripped_zw = strip_zero_width(text)
    if stripped_zw != text:
        add(stripped_zw, "zero_width_stripped")
    # Styled alphabets (𝐼𝑔𝑛𝑜𝑟𝑒, ℐℊ𝓃ℴ𝓇ℯ, ｆｕｌｌｗｉｄｔｈ) fold to ASCII under NFKC, so
    # every detector also sees the plain-text instruction.
    folded = unicodedata.normalize("NFKC", stripped_zw)
    if folded != stripped_zw:
        add(folded, "nfkc_folded")
        stripped_zw = folded

    for step, fold in (
        ("confusables_folded", fold_confusables),
        ("leet_folded", fold_leet),
        ("rot13_decoded", decode_rot13),
    ):
        candidate = fold(stripped_zw)
        if candidate != stripped_zw:
            add(candidate, step)

    for candidate in (text, stripped_zw):
        unwrapped = strip_adversarial_wrappers(candidate)
        if unwrapped != candidate:
            add(unwrapped, "wrapper_stripped")
        for segment in decode_base64_segments(candidate):
            add(segment, "base64_decoded")
            inner = strip_adversarial_wrappers(segment)
            if inner != segment:
                add(inner, "wrapper_stripped")

    return surfaces, applied
