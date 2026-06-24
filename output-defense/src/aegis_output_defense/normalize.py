"""Decode-and-rescan normalization for obfuscated model output."""

from __future__ import annotations

import base64
import re

# Zero-width and other invisible format characters used to break pattern matching.
_ZERO_WIDTH = {0x200B, 0x200C, 0x200D, 0xFEFF, 0x2060}

# Base64 blobs long enough to hide meaningful payload text.
_B64_BLOB = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")


def strip_zero_width(text: str) -> str:
    """Remove zero-width characters that split tokens across pattern matchers."""
    if not any(ord(ch) in _ZERO_WIDTH for ch in text):
        return text
    return "".join(ch for ch in text if ord(ch) not in _ZERO_WIDTH)


def decode_base64_segments(text: str) -> list[str]:
    """Extract and decode embedded base64 blobs (mirrors input-defense heuristic)."""
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

    for segment in decode_base64_segments(content):
        add(segment, "base64_decoded")
    if stripped != content:
        for segment in decode_base64_segments(stripped):
            add(segment, "base64_decoded")

    return surfaces, applied


def prepare_scan_content(content: str) -> tuple[str, list[str]]:
    """Single combined scan string (original + normalized segments)."""
    surfaces, applied = expand_scan_surfaces(content)
    if len(surfaces) == 1:
        return surfaces[0], applied
    return "\n---\n".join(surfaces), applied
