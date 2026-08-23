export type IntakeAnswer = {
  question_id?: string | null;
  category: string;
  value: string;
};

export type RegisterResponse = {
  tenant_id: string;
  slug: string;
  tier: string;
  api_key: string;
};

export type InfraProfileItem = {
  id?: string | null;
  category: string;
  normalized_value: string;
};

export type InfraProfile = {
  tenant_id: string;
  items: InfraProfileItem[];
};

export type AskAnswer = {
  type: "answer";
  answer: string;
  disclaimer: string;
  retrieved: Array<{
    category: string;
    normalized_value: string;
    score: number;
  }>;
  cve_matches: Array<{
    cve_id: string;
    severity: string;
    summary: string;
    matched_value: string;
  }>;
  walkthrough: boolean;
};

export type AskUpsell = {
  type: "upsell";
  feature: "walkthrough";
  message: string;
  upgrade_hint: string;
  policy_action: string;
};

export type AskResponse = AskAnswer | AskUpsell;

export type UsageDiscrepancy = {
  usage_event_id: string;
  event_type: string;
  audit_receipt_id: string | null;
  reason: string;
};

export type UsageSummary = {
  tenant_id: string;
  start_time: string | null;
  end_time: string | null;
  qa_ask_count: number;
  walkthrough_grant_count: number;
  usage_events_total: number;
  receipts_matched: number;
  discrepancies: UsageDiscrepancy[];
  integrity: "ok" | "discrepancies_present";
};
