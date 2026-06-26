"""Generate new attack variants from successful bypass payloads."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from aegis_redteam.models import DefenseTarget, ProbeResult
from aegis_redteam.mutation.strategies import apply_strategy

# Mutators applied to bypass payloads in adaptive rounds (exclude identity).
ADAPTIVE_MUTATORS: tuple[str, ...] = (
    "paraphrase",
    "roleplay",
    "indirect",
    "multi_turn",
    "zero_width",
    "encoding",
    "base64",
)


@dataclass(frozen=True)
class AdaptiveVariant:
    attack_id: str
    category: str
    target: DefenseTarget
    strategy: str
    payload: str
    source_attack_id: str
    source_strategy: str
    round_number: int


def _payload_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def generate_variants_from_bypasses(
    bypasses: list[ProbeResult],
    *,
    round_number: int,
    max_per_bypass: int = 5,
) -> list[AdaptiveVariant]:
    """Mutate successful bypass payloads with strategies different from the one that succeeded."""
    seen: set[str] = set()
    variants: list[AdaptiveVariant] = []

    for bypass in bypasses:
        mutators = [m for m in ADAPTIVE_MUTATORS if m != bypass.strategy]
        applied = 0
        for mutator in mutators:
            if applied >= max_per_bypass:
                break
            payload = apply_strategy(mutator, bypass.payload)
            digest = _payload_hash(payload)
            if digest in seen:
                continue
            seen.add(digest)
            variants.append(
                AdaptiveVariant(
                    attack_id=f"{bypass.attack_id}-r{round_number}-{mutator}",
                    category=bypass.category,
                    target=bypass.target,
                    strategy=f"adaptive:{mutator}",
                    payload=payload,
                    source_attack_id=bypass.attack_id,
                    source_strategy=bypass.strategy,
                    round_number=round_number,
                )
            )
            applied += 1

    return variants
