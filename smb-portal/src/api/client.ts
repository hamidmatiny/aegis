import type {
  AskResponse,
  InfraProfile,
  IntakeAnswer,
  RegisterResponse,
  UsageSummary,
} from "./types";

const API_BASE = "/api/smb";

const SESSION_KEY = "aegis_smb_api_key";
const TENANT_KEY = "aegis_smb_tenant";

export type TenantSession = {
  apiKey: string;
  tenantId: string;
  slug: string;
};

export function loadSession(): TenantSession | null {
  const apiKey = sessionStorage.getItem(SESSION_KEY);
  const raw = sessionStorage.getItem(TENANT_KEY);
  if (!apiKey || !raw) return null;
  try {
    const parsed = JSON.parse(raw) as { tenantId: string; slug: string };
    if (!parsed.tenantId || !parsed.slug) return null;
    return { apiKey, tenantId: parsed.tenantId, slug: parsed.slug };
  } catch {
    return null;
  }
}

export function saveSession(session: TenantSession): void {
  sessionStorage.setItem(SESSION_KEY, session.apiKey);
  sessionStorage.setItem(
    TENANT_KEY,
    JSON.stringify({ tenantId: session.tenantId, slug: session.slug }),
  );
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(TENANT_KEY);
}

export class ApiError extends Error {
  status: number;
  body: string;

  constructor(status: number, body: string) {
    super(body || `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function fetchJSON<T>(
  path: string,
  init: RequestInit = {},
  auth = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    const session = loadSession();
    if (!session?.apiKey) {
      throw new ApiError(401, "missing tenant API key — complete onboarding first");
    }
    headers.set("Authorization", `Bearer ${session.apiKey}`);
  }

  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!resp.ok) {
    const body = await resp.text();
    throw new ApiError(resp.status, body || resp.statusText);
  }
  return resp.json() as Promise<T>;
}

export const smbApi = {
  register: (slug: string, tier = "standard") =>
    fetchJSON<RegisterResponse>(
      "/onboarding/register",
      {
        method: "POST",
        body: JSON.stringify({ slug, tier }),
      },
      false,
    ),

  intake: (answers: IntakeAnswer[]) =>
    fetchJSON<InfraProfile>("/onboarding/intake", {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),

  ask: (question: string, walkthrough = false) =>
    fetchJSON<AskResponse>("/qa/ask", {
      method: "POST",
      body: JSON.stringify({ question, walkthrough }),
    }),

  usage: (params?: { start_time?: string; end_time?: string }) => {
    const qs = new URLSearchParams();
    if (params?.start_time) qs.set("start_time", params.start_time);
    if (params?.end_time) qs.set("end_time", params.end_time);
    const suffix = qs.toString() ? `?${qs}` : "";
    return fetchJSON<UsageSummary>(`/billing/usage${suffix}`);
  },
};
