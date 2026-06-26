"""Generate new attack variants from prior-round probe results."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from aegis_redteam.clients.model_router import ModelRouterClient
from aegis_redteam.models import DefenseTarget, ProbeResult
from aegis_redteam.mutation.router_rephrase import rephrase_blocked_payload
from aegis_redteam.mutation.strategies import apply_strategy

# Mechanical mutators applied to successful bypass payloads (exclude identity).
LEXICAL_MUTATORS: tuple[str, ...] = (
    "paraphrase",
    "roleplay",
    "indirect",
    "multi_turn",
    "zero_width",
    "encoding",
    "base64",
)

ROUTER_BLOCKED_STRATEGY = "adaptive:router_rephrase"
ROUTER_BYPASS_STRATEGY = "adaptive:router_evolve"


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
    mutation_kind: str = "lexical"


def _payload_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def generate_lexical_variants_from_bypasses(
    bypasses: list[ProbeResult],
    *,
    round_number: int,
    max_per_bypass: int = 4,
) -> list[AdaptiveVariant]:
    """Apply mechanical mutators to payloads that evaded defense in the prior round."""
    seen: set[str] = set()
    variants: list[AdaptiveVariant] = []

    for bypass in bypasses:
        source_strategy = bypass.strategy.removeprefix("adaptive:")
        mutators = [m for m in LEXICAL_MUTATORS if m != source_strategy]
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
                    attack_id=f"{bypass.attack_id}-r{round_number}-lex-{mutator}",
                    category=bypass.category,
                    target=bypass.target,
                    strategy=f"adaptive:{mutator}",
                    payload=payload,
                    source_attack_id=bypass.attack_id,
                    source_strategy=bypass.strategy,
                    round_number=round_number,
                    mutation_kind="lexical",
                )
            )
            applied += 1

    return variants


async def generate_router_variants(
    probes: list[ProbeResult],
    *,
    round_number: int,
    client: ModelRouterClient,
    max_blocked: int = 15,
    max_bypass: int = 5,
) -> list[AdaptiveVariant]:
    """
    LLM-adaptive mutations via model-router.

    Prioritizes payloads that were BLOCKED (real adaptive attacker behavior),
    then optionally evolves successful bypasses.
    """
    seen: set[str] = set()
    variants: list[AdaptiveVariant] = []

    blocked = [p for p in probes if not p.bypassed]
    bypasses = [p for p in probes if p.bypassed]

    for probe in blocked[:max_blocked]:
        try:
            payload = await rephrase_blocked_payload(client, probe.payload, was_blocked=True)
        except Exception:
            continue
        digest = _payload_hash(payload)
        if digest in seen or digest == _payload_hash(probe.payload):
            continue
        seen.add(digest)
        variants.append(
            AdaptiveVariant(
                attack_id=f"{probe.attack_id}-r{round_number}-router-blocked",
                category=probe.category,
                target=probe.target,
                strategy=ROUTER_BLOCKED_STRATEGY,
                payload=payload,
                source_attack_id=probe.attack_id,
                source_strategy=probe.strategy,
                round_number=round_number,
                mutation_kind="router_rephrase",
            )
        )

    for probe in bypasses[:max_bypass]:
        try:
            payload = await rephrase_blocked_payload(client, probe.payload, was_blocked=False)
        except Exception:
            continue
        digest = _payload_hash(payload)
        if digest in seen or digest == _payload_hash(probe.payload):
            continue
        seen.add(digest)
        variants.append(
            AdaptiveVariant(
                attack_id=f"{probe.attack_id}-r{round_number}-router-evolve",
                category=probe.category,
                target=probe.target,
                strategy=ROUTER_BYPASS_STRATEGY,
                payload=payload,
                source_attack_id=probe.attack_id,
                source_strategy=probe.strategy,
                round_number=round_number,
                mutation_kind="router_evolve",
            )
        )

    return variants


async def generate_adaptive_variants(
    prior_round_probes: list[ProbeResult],
    *,
    round_number: int,
    max_lexical_per_bypass: int = 4,
    router_client: ModelRouterClient | None = None,
    max_router_blocked: int = 15,
    max_router_bypass: int = 5,
) -> list[AdaptiveVariant]:
    """Combine lexical bypass mutations and LLM router rephrases for one adaptive round."""
    bypasses = [p for p in prior_round_probes if p.bypassed]
    variants = generate_lexical_variants_from_bypasses(
        bypasses,
        round_number=round_number,
        max_per_bypass=max_lexical_per_bypass,
    )

    if router_client is not None:
        router_variants = await generate_router_variants(
            prior_round_probes,
            round_number=round_number,
            client=router_client,
            max_blocked=max_router_blocked,
            max_bypass=max_router_bypass,
        )
        seen = {_payload_hash(v.payload) for v in variants}
        for variant in router_variants:
            digest = _payload_hash(variant.payload)
            if digest not in seen:
                seen.add(digest)
                variants.append(variant)

    return variants
