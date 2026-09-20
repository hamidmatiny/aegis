"""Match retrieved infra values against the seeded CVE reference table."""

from __future__ import annotations

import re
from dataclasses import dataclass

from aegis_smb_copilot.db.connection import get_pool

# Map inventory tokens → curated product_pattern aliases (exact rows in cve_reference).
_PATTERN_ALIASES: dict[str, tuple[str, ...]] = {
    "digitalocean-droplets": ("digitalocean",),
    "digitalocean-droplet": ("digitalocean",),
    "do-droplets": ("digitalocean",),
    "microsoft-365.x": ("microsoft-365", "office365", "m365"),
    "microsoft-365": ("office365", "m365"),
    "office-365.x": ("microsoft-365", "office365", "m365"),
    "office-365": ("microsoft-365", "office365", "m365"),
    "m365.x": ("microsoft-365", "office365", "m365"),
    "wordpress": ("wordpress-6.x",),
    "ubuntu-20.04.x": ("ubuntu-20.04", "ubuntu"),
    "ubuntu-22.04.x": ("ubuntu-22.04", "ubuntu"),
    "windows-server-2019.x": ("windows-server", "windows-rdp"),
    "windows-server-2022.x": ("windows-server", "windows-rdp"),
}

_VERSIONED_RE = re.compile(
    r"^(?P<name>[a-z][a-z0-9_+-]*)-(?P<major>\d+)(?:\.(?P<minor>\d+))?\.x$"
)


@dataclass(frozen=True)
class CVEMatch:
    product_pattern: str
    cve_id: str
    severity: str
    summary: str
    matched_value: str


def candidate_patterns(normalized_value: str) -> list[str]:
    """Expand an inventory token so curated major/product rows can match.

    Real gap this closes: intake stores ``postgres-14.5.x`` while ``cve_reference``
    seeds ``postgres-14.x`` — exact equality previously returned zero hits.
    """
    value = (normalized_value or "").strip().lower()
    if not value:
        return []
    out: list[str] = [value]
    for alias in _PATTERN_ALIASES.get(value, ()):
        out.append(alias)

    m = _VERSIONED_RE.match(value)
    if m:
        name = m.group("name")
        major = m.group("major")
        minor = m.group("minor")
        out.append(f"{name}-{major}.x")
        out.append(name)
        if minor is not None:
            out.append(f"{name}-{major}.{minor}.x")
        for alias in _PATTERN_ALIASES.get(f"{name}-{major}.x", ()):
            out.append(alias)
        for alias in _PATTERN_ALIASES.get(name, ()):
            out.append(alias)

    # de-dupe, preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for p in out:
        if p and p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def match_cves(normalized_values: list[str]) -> list[CVEMatch]:
    """Return CVE rows matching inventory values (exact or expanded parent/alias)."""
    value_list = sorted({v.strip() for v in normalized_values if v and v.strip()})
    if not value_list:
        return []

    # Map candidate pattern → original inventory values that expand to it
    pattern_to_values: dict[str, set[str]] = {}
    all_patterns: set[str] = set()
    for value in value_list:
        for pat in candidate_patterns(value):
            all_patterns.add(pat)
            pattern_to_values.setdefault(pat, set()).add(value)

    if not all_patterns:
        return []

    pool = get_pool()
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT product_pattern, cve_id, severity, summary
            FROM cve_reference
            WHERE product_pattern = ANY(%s)
            ORDER BY severity DESC, cve_id ASC
            """,
            (sorted(all_patterns),),
        ).fetchall()

    matches: list[CVEMatch] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for product_pattern, cve_id, severity, summary in rows:
        pattern = str(product_pattern)
        for inventory_value in sorted(pattern_to_values.get(pattern, set())):
            key = (str(cve_id), pattern, inventory_value)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            matches.append(
                CVEMatch(
                    product_pattern=pattern,
                    cve_id=str(cve_id),
                    severity=str(severity),
                    summary=str(summary),
                    matched_value=inventory_value,
                )
            )
    return matches


def list_tenant_normalized_values(tenant_id) -> list[str]:
    """All infra_memory normalized_value tokens for a tenant (CVE match input)."""
    pool = get_pool()
    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT normalized_value
            FROM infra_memory
            WHERE tenant_id = %s
            ORDER BY normalized_value
            LIMIT 100
            """,
            (tenant_id,),
        ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]
