"""Orchestrate retrieval, CVE matching, and model-router chat for /qa/ask."""

from __future__ import annotations

from uuid import UUID

from aegis_smb_copilot.billing.usage_recorder import (
    EVENT_QA_ASK,
    EVENT_WALKTHROUGH_GRANT,
    record_usage_event,
)
from aegis_smb_copilot import config
from aegis_smb_copilot.clients.model_router import chat_completion
from aegis_smb_copilot.qa.cve_match import list_tenant_normalized_values, match_cves
from aegis_smb_copilot.qa.retrieval import retrieve_infra_context
from aegis_smb_copilot.qa.schema import (
    QA_DISCLAIMER,
    AskResponse,
    CVEHit,
    RetrievedItem,
    cve_hit_from_match,
)
from aegis_smb_copilot.analytics.funnel import emit_funnel_event


def ask(tenant_id: UUID, question: str, *, walkthrough: bool = False) -> AskResponse:
    """Return advisory text grounded in tenant infra memory (no actions taken)."""
    memories = retrieve_infra_context(tenant_id, question)
    # Match CVEs against the full inventory (not only top-K retrieval) so a
    # postgres question still surfaces postgres-14.x rows even if ranking is noisy.
    inventory_values = list_tenant_normalized_values(tenant_id)
    retrieved_values = [m.normalized_value for m in memories]
    cves = match_cves(inventory_values or retrieved_values)

    context_lines = [
        f"- {m.category}: {m.normalized_value} (score={m.score:.3f})" for m in memories
    ]
    inventory_lines = [f"- {v}" for v in inventory_values]
    cve_lines = [
        f"- {c.cve_id} [{c.severity}] on {c.matched_value} (pattern {c.product_pattern}): {c.summary}"
        for c in cves
    ]
    if walkthrough:
        system = (
            "You are AEGIS's advisory walkthrough assistant — an applied example "
            "on top of the AEGIS LLM security gateway (policy, audit, human gate), "
            "not an autonomous agent. Produce a numbered, step-by-step plan grounded "
            "in the tenant infrastructure profile and curated CVE notes below. "
            "Name the specific products/versions from the profile. If a CVE row is "
            "listed, cite its ID. If the curated reference has no row, say so plainly "
            "and still give practical hardening advice for the listed inventory — "
            "do not invent CVE IDs. Do not claim to have applied changes or run tools."
        )
    else:
        system = (
            "You are AEGIS's free-tier advisory Q&A assistant — an applied example "
            "on top of the AEGIS LLM security gateway (policy, audit, human gate), "
            "not an autonomous agent or full product pitch. Ground every answer in "
            "the tenant infrastructure profile and curated CVE notes below. Name "
            "specific products/versions from the profile when present. If a CVE row "
            "is listed, cite its ID and severity. If the curated reference has no "
            "matching row, say the curated reference has no match — do not invent "
            "CVE IDs — and still give concise practical advice for the listed "
            "inventory. Do not claim to have applied changes or run tools."
        )
    user = (
        f"Question:\n{question.strip()}\n\n"
        f"Tenant infrastructure (full inventory):\n"
        + ("\n".join(inventory_lines) if inventory_lines else "(empty — user has not completed setup)")
        + "\n\nTenant infrastructure (retrieval ranking for this question):\n"
        + ("\n".join(context_lines) if context_lines else "(none retrieved)")
        + "\n\nRelevant curated CVE / advisory flags:\n"
        + ("\n".join(cve_lines) if cve_lines else "(none in curated reference for this inventory)")
    )
    if walkthrough:
        chat_model = config.settings.chat_model_walkthrough
        max_tokens = config.settings.qa_max_tokens_walkthrough
    else:
        chat_model = config.settings.chat_model
        max_tokens = config.settings.qa_max_tokens_free

    answer = chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=chat_model,
        max_tokens=max_tokens,
    )

    # Always bill an ask; walkthrough grants are an additional paid event.
    record_usage_event(tenant_id, EVENT_QA_ASK)
    if walkthrough:
        record_usage_event(tenant_id, EVENT_WALKTHROUGH_GRANT)

    emit_funnel_event(
        "qa_asked",
        path="/chat" if not walkthrough else "/walkthrough",
        meta={
            "walkthrough": walkthrough,
            "retrieved_count": len(memories),
            "inventory_count": len(inventory_values),
            "cve_match_count": len(cves),
        },
    )
    if cves:
        emit_funnel_event(
            "cve_match_shown",
            path="/chat" if not walkthrough else "/walkthrough",
            meta={
                "cve_ids": [c.cve_id for c in cves[:20]],
                "count": len(cves),
            },
        )

    return AskResponse(
        answer=answer,
        disclaimer=QA_DISCLAIMER,
        retrieved=[
            RetrievedItem(
                category=m.category,
                normalized_value=m.normalized_value,
                score=m.score,
            )
            for m in memories
        ],
        cve_matches=[cve_hit_from_match(c) for c in cves],
        walkthrough=walkthrough,
    )


# Re-export for type checkers / tests
__all__ = ["ask", "AskResponse", "CVEHit", "QA_DISCLAIMER"]
