"""Decode-and-rescan normalization for obfuscated model output."""

from __future__ import annotations

import base64
import re

# Zero-width and other invisible format characters used to break pattern matching.
_ZERO_WIDTH = {0x200B, 0x200C, 0x200D, 0xFEFF, 0x2060}

# Base64 blobs long enough to hide meaningful payload text.
_B64_BLOB = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")

# Jailbreak / indirection wrappers that hide the inner payload from
# detectors. Class-level prefixes (hypothetical, persona, tool result,
# multi-turn, decode-hint), not a single campaign string.
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
    re.compile(r"^for a tabletop rpg[:\s-]*", re.I),
    re.compile(r"^as a forensic novelist[,\s-]*", re.I),
    re.compile(
        r"^(?:safety|content)?\s*(?:guardrails?|policies?|filters?)\s+"
        r"(?:are\s+)?(?:disabled|waived|turned off|off)\.?\s*"
        r"(?:here is (?:the )?unrestricted response(?: about)?[:.\s-]*)?",
        re.I,
    ),
    re.compile(
        r"^content policy waived(?: for this thread)?\.?\s*"
        r"(?:below are the steps to|here (?:is|are)|the following)[:.\s-]*",
        re.I,
    ),
    re.compile(
        r"^i(?:'m| am)?\s+(?:not allowed|unable|not supposed)\s+to\s+"
        r"(?:help with|assist with|discuss).{0,60}?\.\s*"
        r"(?:that said|however|but|nonetheless)[,:\s-]*",
        re.I | re.S,
    ),
)


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


def strip_zero_width(text: str) -> str:
    """Remove zero-width characters that split tokens across pattern matchers."""
    if not any(ord(ch) in _ZERO_WIDTH for ch in text):
        return text
    return "".join(ch for ch in text if ord(ch) not in _ZERO_WIDTH)


def decode_base64_segments(text: str) -> list[str]:
    """Extract and decode embedded base64 blobs (mirrors input-defense heuristic)."""
    decoded: list[str] = []
    seen: set[str] = set()

    def _try_blobs(source: str) -> None:
        for blob in _B64_BLOB.findall(source):
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

    _try_blobs(text)
    # Unicode/ZW pollution can break contiguous base64 runs; retry on alphabet-only.
    filtered = "".join(ch for ch in text if ch.isalnum() or ch in "+/=")
    if filtered != text:
        _try_blobs(filtered)
    return decoded


def expand_scan_surfaces(content: str) -> tuple[list[str], list[str]]:
    """
    Build scan surfaces: original, zero-width-stripped, and base64-decoded variants.

    Returns (surfaces, normalization_steps_applied).
    """
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

    add(content)
    stripped = strip_zero_width(content)
    if stripped != content:
        add(stripped, "zero_width_stripped")

    for candidate in (content, stripped):
        unwrapped = strip_adversarial_wrappers(candidate)
        if unwrapped != candidate:
            add(unwrapped, "wrapper_stripped")
            unwrapped_zw = strip_zero_width(unwrapped)
            if unwrapped_zw != unwrapped:
                add(unwrapped_zw, "zero_width_stripped")
        for segment in decode_base64_segments(candidate):
            add(segment, "base64_decoded")
            segment_zw = strip_zero_width(segment)
            if segment_zw != segment:
                add(segment_zw, "zero_width_stripped")
            inner = strip_adversarial_wrappers(segment_zw)
            if inner != segment_zw:
                add(inner, "wrapper_stripped")

    return surfaces, applied


def prepare_scan_content(content: str) -> tuple[str, list[str]]:
    """Single combined scan string (original + normalized segments)."""
    surfaces, applied = expand_scan_surfaces(content)
    if len(surfaces) == 1:
        return surfaces[0], applied
    return "\n---\n".join(surfaces), applied
