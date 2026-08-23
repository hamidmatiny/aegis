"""Q&A request/response models — disclaimer is mandatory."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from aegis_smb_copilot.qa.cve_match import CVEMatch

# Product-liability control: always present, never empty.
QA_DISCLAIMER = (
    "This is automated advisory guidance from AEGIS SMB Copilot, not a guaranteed "
    "fix or professional security assessment. Production-impacting changes should "
    "be reviewed and approved by a qualified professional before implementation."
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class RetrievedItem(BaseModel):
    category: str
    normalized_value: str
    score: float


class CVEHit(BaseModel):
    cve_id: str
    severity: str
    summary: str
    matched_value: str


class AskResponse(BaseModel):
    answer: str
    disclaimer: str = Field(..., min_length=1)
    retrieved: list[RetrievedItem] = Field(default_factory=list)
    cve_matches: list[CVEHit] = Field(default_factory=list)

    @field_validator("disclaimer")
    @classmethod
    def disclaimer_must_be_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("disclaimer must be a non-empty string")
        return stripped


def cve_hit_from_match(match: CVEMatch) -> CVEHit:
    return CVEHit(
        cve_id=match.cve_id,
        severity=match.severity,
        summary=match.summary,
        matched_value=match.matched_value,
    )
