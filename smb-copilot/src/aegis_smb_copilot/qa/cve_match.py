"""Match retrieved infra values against the seeded CVE reference table."""

from __future__ import annotations

from dataclasses import dataclass

from aegis_smb_copilot.db.connection import get_pool


@dataclass(frozen=True)
class CVEMatch:
    product_pattern: str
    cve_id: str
    severity: str
    summary: str
    matched_value: str


def match_cves(normalized_values: list[str]) -> list[CVEMatch]:
    """Return CVE rows whose ``product_pattern`` equals a retrieved normalized value."""
    values = sorted({v.strip() for v in normalized_values if v and v.strip()})
    if not values:
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
            (values,),
        ).fetchall()

    matches: list[CVEMatch] = []
    value_set = set(values)
    for product_pattern, cve_id, severity, summary in rows:
        pattern = str(product_pattern)
        if pattern not in value_set:
            continue
        matches.append(
            CVEMatch(
                product_pattern=pattern,
                cve_id=str(cve_id),
                severity=str(severity),
                summary=str(summary),
                matched_value=pattern,
            )
        )
    return matches
