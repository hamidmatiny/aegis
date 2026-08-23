"""Billing routes (scaffold). Walkthrough entitlement lives in policy-engine CEL."""

from fastapi import APIRouter

router = APIRouter(prefix="/billing", tags=["billing"])
