"""AEGIS SDK — drop-in OpenAI/Anthropic wrappers with defense-in-depth."""

from aegis_sdk.anthropic_client import Anthropic
from aegis_sdk.errors import (
    AegisApprovalRequiredError,
    AegisError,
    AegisPolicyBlockedError,
    AegisProviderError,
)
from aegis_sdk.openai_client import OpenAI

__all__ = [
    "Anthropic",
    "OpenAI",
    "AegisError",
    "AegisPolicyBlockedError",
    "AegisProviderError",
    "AegisApprovalRequiredError",
]

__version__ = "0.1.0"
