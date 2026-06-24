import type {
  ApprovalRequest,
  AuditReceipt,
  CampaignSummary,
  DryRunResponse,
  PolicyPack,
} from "./types";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(body || resp.statusText);
  }
  return resp.json() as Promise<T>;
}

export const auditApi = {
  query: (params: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString();
    return fetchJSON<{ receipts: AuditReceipt[] }>(`/api/audit/v1/receipts?${qs}`);
  },
  verify: (id: string) =>
    fetchJSON<{ valid: boolean; reason?: string }>(`/api/audit/v1/receipts/${id}/verify`),
  export: (body: Record<string, unknown>) =>
    fetch("/api/audit/v1/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};

export const policyApi = {
  listPacks: () =>
    fetchJSON<{ policy_packs: PolicyPack[] }>("/api/policy/v1/policy-packs"),
  getPack: (id: string) =>
    fetchJSON<{ pack: PolicyPack; source_yaml: string }>(
      `/api/policy/v1/policy-packs/${id}`,
    ),
  dryRun: (body: {
    yaml: string;
    rule_set: string;
    sample?: unknown;
  }) =>
    fetchJSON<DryRunResponse>("/api/policy/v1/dry-run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};

export const agentGateApi = {
  listApprovals: (status: "pending" | "all" = "pending") =>
    fetchJSON<{ approvals: ApprovalRequest[] }>(
      `/api/agent-gate/v1/approvals${status === "all" ? "?status=all" : ""}`,
    ),
  decide: (id: string, approved: boolean, reviewerId: string, comment?: string) =>
    fetchJSON<{ decision: unknown }>(`/api/agent-gate/v1/approvals/${id}/decide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved, reviewer_id: reviewerId, comment }),
    }),
  createPendingApproval: () =>
    fetchJSON<{ decision: { approval_request_id?: string } }>(
      "/api/agent-gate/v1/evaluate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_id: "default",
          tool_call: {
            tool_name: "delete_database",
            risk_level: "IRREVERSIBLE",
            arguments: [{ name: "target", taint_level: "TRUSTED" }],
          },
        }),
      },
    ),
};

export const redteamApi = {
  listCampaigns: () =>
    fetchJSON<{ campaigns: CampaignSummary[] }>("/api/redteam/v1/campaigns"),
  runCampaign: () =>
    fetchJSON<{ report: CampaignSummary }>("/api/redteam/v1/campaigns/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        targets: ["input_defense", "output_defense"],
        strategies: ["identity"],
        store_bypasses: false,
      }),
    }),
};

export function isBlockedReceipt(receipt: AuditReceipt): boolean {
  const payloads = [
    receipt.input_verdict,
    receipt.output_verdict,
    receipt.policy_decision,
    receipt.tool_decision,
  ];
  for (const p of payloads) {
    if (!p) continue;
    const action = String(p.action ?? p.status ?? "").toUpperCase();
    if (["BLOCK", "DENIED", "ESCALATE", "ESCALATE_TO_JUDGE", "AWAITING_HUMAN_APPROVAL"].includes(action)) {
      return true;
    }
    if (typeof p.fused_score === "number" && p.fused_score >= 0.85) {
      return true;
    }
  }
  return false;
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

export function pct(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}
