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
from aegis_smb_copilot.qa.cve_match import match_cves
from aegis_smb_copilot.qa.retrieval import retrieve_infra_context
from aegis_smb_copilot.qa.schema import (
    QA_DISCLAIMER,
    AskResponse,
    CVEHit,
    RetrievedItem,
    cve_hit_from_match,
)


def ask(tenant_id: UUID, question: str, *, walkthrough: bool = False) -> AskResponse:
    """Return advisory text grounded in tenant infra memory (no actions taken)."""
    memories = retrieve_infra_context(tenant_id, question)
    values = [m.normalized_value for m in memories]
    cves = match_cves(values)

    context_lines = [
        f"- {m.category}: {m.normalized_value} (score={m.score:.3f})" for m in memories
    ]
    cve_lines = [
        f"- {c.cve_id} [{c.severity}] on {c.matched_value}: {c.summary}" for c in cves
    ]
    if walkthrough:
        system = (
            "You are AEGIS SMB Copilot providing a paid guided walkthrough. "
            "Produce a numbered, step-by-step plan using only the provided "
            "infrastructure profile and CVE notes. Do not claim to have applied "
            "changes or run tools. Be concrete and practical."
        )
    else:
        system = (
            "You are AEGIS SMB Copilot, a free-tier advisory assistant for small businesses. "
            "Answer only from the provided infrastructure profile and CVE notes. "
            "Do not claim to have applied changes or run tools. Be concise and practical."
        )
    user = (
        f"Question:\n{question.strip()}\n\n"
        f"Tenant infrastructure (retrieved):\n"
        + ("\n".join(context_lines) if context_lines else "(none retrieved)")
        + "\n\nRelevant CVE flags:\n"
        + ("\n".join(cve_lines) if cve_lines else "(none)")
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
