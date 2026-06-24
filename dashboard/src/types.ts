export type AuditReceipt = {
  receipt_id: string;
  event_type: string;
  tenant_id: string;
  trace?: { trace_id?: string; request_id?: string };
  input_verdict?: Record<string, unknown>;
  output_verdict?: Record<string, unknown>;
  policy_decision?: Record<string, unknown>;
  tool_decision?: Record<string, unknown>;
  created_at: string;
  payload_hash?: string;
  signer_key_id?: string;
};

export type PolicyPack = {
  id: string;
  version: string;
  tenant_id: string;
  description?: string;
  input_rules?: PolicyRule[];
  output_rules?: PolicyRule[];
  tool_rules?: PolicyRule[];
};

export type PolicyRule = {
  id: string;
  name: string;
  cel: string;
  action: string;
  enabled: boolean;
};

export type ApprovalRequest = {
  approval_id: string;
  tenant_id: string;
  status: string;
  created_at: string;
  expires_at: string;
  tool_call: {
    tool_name: string;
    risk_level?: string;
    arguments?: Array<{ name: string; taint_level?: string }>;
  };
  reviewer_id?: string;
  review_comment?: string;
};

export type CampaignSummary = {
  campaign_id: string;
  started_at: string;
  completed_at: string;
  total_probes: number;
  bypass_count: number;
  bypass_rate: number;
  by_target: Record<
    string,
    { target: string; probes: number; bypasses: number; bypass_rate: number }
  >;
};

export type DryRunResponse = {
  valid: boolean;
  error?: string;
  decision?: {
    action: string;
    matched_rules: Array<{ rule_id: string; matched: boolean }>;
    block_reason?: string;
    mode: string;
  };
};
