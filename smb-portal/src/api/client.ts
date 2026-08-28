import type {
  AskResponse,
  InfraProfile,
  IntakeAnswer,
  RegisterResponse,
  UsageSummary,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/smb";

const GUEST_SESSION_KEY = "aegis_smb_api_key";
const GUEST_TENANT_KEY = "aegis_smb_tenant";

/** Guest onboarding still stores API key in sessionStorage (unchanged flow). */
export type GuestSession = {
  apiKey: string;
  tenantId: string;
  slug: string;
};

export function loadGuestSession(): GuestSession | null {
  const apiKey = sessionStorage.getItem(GUEST_SESSION_KEY);
  const raw = sessionStorage.getItem(GUEST_TENANT_KEY);
  if (!apiKey || !raw) return null;
  try {
    const parsed = JSON.parse(raw) as { tenantId: string; slug: string };
    if (!parsed.tenantId || !parsed.slug) return null;
    return { apiKey, tenantId: parsed.tenantId, slug: parsed.slug };
  } catch {
    return null;
  }
}

export function saveGuestSession(session: GuestSession): void {
  sessionStorage.setItem(GUEST_SESSION_KEY, session.apiKey);
  sessionStorage.setItem(
    GUEST_TENANT_KEY,
    JSON.stringify({ tenantId: session.tenantId, slug: session.slug }),
  );
}

export function clearGuestSession(): void {
  sessionStorage.removeItem(GUEST_SESSION_KEY);
  sessionStorage.removeItem(GUEST_TENANT_KEY);
}

export type CustomerMe = {
  role: "customer";
  email: string;
  tenant_id: string;
  slug: string;
  tier: string;
};

export type AdminMe = {
  role: "admin";
  username: string;
};

export type GuestMe = {
  role: "guest";
};

export type AuthMe = CustomerMe | AdminMe | GuestMe;

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
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }

  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new ApiError(resp.status, body || resp.statusText);
  }
  if (resp.status === 204) {
    return undefined as T;
  }
  return resp.json() as Promise<T>;
}

export const smbApi = {
  me: () => fetchJSON<AuthMe>("/auth/me"),

  registerAccount: (email: string, password: string, slug?: string) =>
    fetchJSON<{ tenant_id: string; slug: string; api_key: string; email: string }>(
      "/auth/register",
      {
        method: "POST",
        body: JSON.stringify({ email, password, slug: slug || undefined }),
      },
    ),

  login: (email: string, password: string) =>
    fetchJSON<{ status: string; role: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  adminLogin: (username: string, password: string) =>
    fetchJSON<{ status: string; role: string }>("/auth/admin-login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  logout: () =>
    fetchJSON<{ status: string }>("/auth/logout", { method: "POST" }),

  register: (slug: string, tier = "standard") =>
    fetchJSON<RegisterResponse>(
      "/onboarding/register",
      {
        method: "POST",
        body: JSON.stringify({ slug, tier }),
      },
    ),

  intake: (answers: IntakeAnswer[]) => {
    const guest = loadGuestSession();
    const headers: Record<string, string> = {};
    if (guest?.apiKey) {
      headers.Authorization = `Bearer ${guest.apiKey}`;
    }
    return fetchJSON<InfraProfile>("/onboarding/intake", {
      method: "POST",
      body: JSON.stringify({ answers }),
      headers,
    });
  },

  ask: (question: string, walkthrough = false) => {
    const guest = loadGuestSession();
    const headers: Record<string, string> = {};
    if (guest?.apiKey) {
      headers.Authorization = `Bearer ${guest.apiKey}`;
    }
    return fetchJSON<AskResponse>("/qa/ask", {
      method: "POST",
      body: JSON.stringify({ question, walkthrough }),
      headers,
    });
  },

  usage: (params?: { start_time?: string; end_time?: string }) => {
    const qs = new URLSearchParams();
    if (params?.start_time) qs.set("start_time", params.start_time);
    if (params?.end_time) qs.set("end_time", params.end_time);
    const suffix = qs.toString() ? `?${qs}` : "";
    return fetchJSON<UsageSummary>(`/billing/usage${suffix}`);
  },

  adminListTenants: () =>
    fetchJSON<{
      tenants: Array<{
        id: string;
        slug: string;
        tier: string;
        email: string | null;
        created_at: string;
        walkthrough_allowed: boolean | null;
      }>;
    }>("/admin/tenants"),

  adminTenantDetail: (tenantId: string) =>
    fetchJSON<{
      id: string;
      slug: string;
      tier: string;
      email: string | null;
      walkthrough_allowed: boolean;
      policy_override_path: string;
      usage: UsageSummary;
    }>(`/admin/tenants/${tenantId}`),

  adminSetTier: (tenantId: string, tier: "free" | "paid") =>
    fetchJSON<unknown>(`/admin/tenants/${tenantId}/tier`, {
      method: "POST",
      body: JSON.stringify({ tier }),
    }),
};

/** @deprecated use loadGuestSession */
export const loadSession = loadGuestSession;
/** @deprecated use saveGuestSession */
export const saveSession = saveGuestSession;
/** @deprecated use clearGuestSession */
export const clearSession = clearGuestSession;
