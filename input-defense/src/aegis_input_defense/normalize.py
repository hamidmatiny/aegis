"""Decode-and-rescan plus jailbreak-wrapper stripping for input text."""

from __future__ import annotations

import base64
import re

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
