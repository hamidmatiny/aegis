"""Auth request/response models."""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,62}$")


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    slug: str | None = Field(
        default=None,
        description="Tenant slug; derived from email local-part when omitted.",
    )

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not _EMAIL_RE.match(email):
            raise ValueError("invalid email address")
        return email

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        slug = value.strip().lower()
        if not _SLUG_RE.match(slug):
            raise ValueError("slug must match ^[a-z0-9][a-z0-9\\-]{0,62}$")
        return slug


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class CustomerMeResponse(BaseModel):
    role: Literal["customer"] = "customer"
    email: str
    tenant_id: UUID
    slug: str
    tier: str


class AdminMeResponse(BaseModel):
    role: Literal["admin"] = "admin"
    username: str


class GuestMeResponse(BaseModel):
    role: Literal["guest"] = "guest"


MeResponse = CustomerMeResponse | AdminMeResponse | GuestMeResponse
