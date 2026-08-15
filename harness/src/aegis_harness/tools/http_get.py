"""http_get -- a MEDIUM-risk starter tool, new in operator-platform phase 2.

New tool_catalog entry (see policy-engine/policies/default.yaml) at
MEDIUM: outbound network access from an agent is a well-known
exfiltration and SSRF (server-side request forgery) vector in real
deployments -- a prompt-injected agent that can make arbitrary outbound
requests can be turned into a proxy for probing internal services or
leaking data to an attacker-controlled endpoint. This tool narrows that
down considerably, but is registered at MEDIUM (the same tier as
send_email) rather than left undeclared, because "makes a real network
call" is exactly the kind of capability this project's tool_catalog
comment says should be registered.

Safety properties, and their honest limits:
  - Fails closed: refuses every request unless its target host is in
    `allowed_domains`, an explicit allowlist the operator configures at
    construction time (default: `["example.com"]`, IANA's reserved
    documentation domain -- RFC 2606 -- chosen specifically so the
    out-of-the-box default can never plausibly reach anything real).
  - What this does NOT do: resolve the hostname and check that the
    resolved IP is actually public. A DNS record for an allowed domain
    that resolves to an internal/private address (a real, known SSRF
    technique) would still be permitted here. A production-grade version
    of this tool would validate the resolved IP as well, not just the
    hostname string -- disclosed here rather than silently assumed safe,
    consistent with this project's practice of not overclaiming a
    security property this starter tool doesn't actually have.
  - Only GET, only a fixed short timeout, only the response body's text
    (truncated) is returned -- no headers, no cookies, no redirects
    followed across a domain not itself on the allowlist.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from aegis_harness.tool import Tool

_MAX_RESPONSE_CHARS = 2000
_TIMEOUT_SECONDS = 10.0


class HttpGetTool(Tool):
    name = "http_get"
    description = (
        "Make a read-only GET request to an allowlisted domain and return "
        "the response body (truncated)."
    )
    risk_level = "MEDIUM"

    def __init__(self, allowed_domains: list[str] | None = None) -> None:
        if allowed_domains is None:
            allowed_domains = ["example.com"]
        self._allowed_domains = set(allowed_domains)

    def argument_schema(self) -> dict[str, Any]:
        return {"url": "string, an https:// URL whose host is on the configured allowlist"}

    def execute(self, arguments: dict[str, Any]) -> str:
        url = str(arguments.get("url", "")).strip()
        if not url:
            return "Error: 'url' is required."
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return "Error: only https:// URLs are allowed."
        host = parsed.hostname or ""
        if host not in self._allowed_domains:
            return (
                f"Error: '{host}' is not on the allowed domain list "
                f"({sorted(self._allowed_domains)}). Refusing the request."
            )
        try:
            resp = httpx.get(url, timeout=_TIMEOUT_SECONDS, follow_redirects=False)
        except httpx.HTTPError as exc:
            return f"Error: request failed -- {exc}"
        body = resp.text[:_MAX_RESPONSE_CHARS]
        suffix = "... [truncated]" if len(resp.text) > _MAX_RESPONSE_CHARS else ""
        return f"HTTP {resp.status_code} from {host}:\n{body}{suffix}"
