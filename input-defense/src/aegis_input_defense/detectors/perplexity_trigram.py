"""Character trigram perplexity stub (Phase 1 reference implementation)."""

from __future__ import annotations

import math
import re

# Character trigram log-probabilities from English text (lightweight reference model).
_TRIGRAM_LOG_PROB: dict[str, float] = {
    " th": -0.35,
    "he ": -0.40,
    "the": -0.30,
    " an": -0.80,
    "nd ": -0.70,
    "ing": -0.55,
    "ion": -0.65,
    " ti": -0.90,
    "to ": -0.75,
    " of": -0.50,
    "of ": -0.55,
    " in": -0.60,
    "in ": -0.65,
    "er ": -0.70,
    " re": -0.85,
    "ed ": -0.75,
    " ou": -0.95,
    "you": -1.00,
    " is": -0.70,
    "is ": -0.75,
    "at ": -0.80,
    " st": -0.90,
    "str": -1.00,
    "tru": -1.10,
    "ruc": -1.20,
    "uct": -1.30,
    " pr": -0.85,
    "pre": -0.95,
    "evi": -1.10,
    "vio": -1.15,
    "ous": -0.90,
    "nst": -1.20,
    " ct": -1.10,
    "tio": -0.95,
    " ig": -1.30,
    "ign": -1.20,
    "gno": -1.40,
    "nor": -1.30,
    "ore": -1.00,
    " ba": -1.00,
    "bas": -1.10,
    "ase": -1.05,
    "se6": -2.50,
    "e64": -2.80,
    "64 ": -2.20,
    " un": -1.00,
    "uni": -1.05,
    "nic": -1.10,
    "ico": -1.15,
    "ode": -1.05,
    "de ": -1.00,
}

_LOG_FLOOR = -2.5


def trigram_sequence_perplexity(text: str) -> float:
    """Compute character trigram perplexity for a text segment."""
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    if len(normalized) < 4:
        return 1.0

    log_sum = 0.0
    count = 0
    padded = f"  {normalized}  "
    for i in range(len(padded) - 2):
        trigram = padded[i : i + 3]
        key = trigram.lower()
        log_sum += _TRIGRAM_LOG_PROB.get(key, _LOG_FLOOR)
        count += 1

    avg_log = log_sum / count
    return math.pow(10, -avg_log)
