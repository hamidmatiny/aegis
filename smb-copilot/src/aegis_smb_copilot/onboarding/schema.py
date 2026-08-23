"""Onboarding request/response models."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class IntakeQuestion(BaseModel):
    """A catalog question shown during SMB infra intake."""

    id: str
    category: str = Field(description="Infra category, e.g. database, cloud, auth")
    prompt: str


class IntakeAnswer(BaseModel):
    """Client answer to an intake question (raw text may be free-form)."""

    question_id: str | None = None
    category: str
    value: str = Field(description="Raw answer text; service normalizes before storage")


class InfraProfileItem(BaseModel):
    """One normalized category/value pair stored for a tenant."""

    id: UUID | None = None
    category: str
    normalized_value: str


class InfraProfile(BaseModel):
    """Normalized infra profile for a tenant (no raw free-text version strings)."""

    tenant_id: UUID
    items: list[InfraProfileItem]


class IntakeRequest(BaseModel):
    answers: list[IntakeAnswer] = Field(min_length=1)


class RegisterRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    tier: str = Field(default="standard", min_length=1, max_length=32)


class RegisterResponse(BaseModel):
    tenant_id: UUID
    slug: str
    tier: str
    api_key: str = Field(description="Shown once; store securely. Subsequent auth uses this key.")
