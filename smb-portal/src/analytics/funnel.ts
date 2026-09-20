/** Anonymous funnel + SPA pageview tracker for Growth conversion. */

const SESSION_KEY = "aegis_funnel_sid";

function sessionId(): string {
  try {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing && existing.length >= 8) return existing;
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `s-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem(SESSION_KEY, id);
    return id;
  } catch {
    return "";
  }
}

export type FunnelEvent =
  | "pageview"
  | "signup_started"
  | "signup_completed"
  | "inventory_saved"
  | "qa_asked"
  | "cve_match_shown"
  | "walkthrough_viewed"
  | "upgrade_viewed"
  | "upgrade_started"
  | "upgrade_completed";

export function trackFunnel(
  event: FunnelEvent,
  opts?: { path?: string; meta?: Record<string, unknown> },
): void {
  try {
    const path = opts?.path ?? window.location.pathname;
    const body = JSON.stringify({
      event,
      path,
      referrer: document.referrer || "",
      title: document.title || "",
      session_id: sessionId(),
      meta: opts?.meta ?? {},
    });
    void fetch("/api/smb/analytics/collect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {});
  } catch {
    // ignore
  }
}

/** Fire pageview on every client-side navigation (React Router soft nav). */
export function installSpaPageviews(getPath: () => string): () => void {
  let last = "";
  const tick = () => {
    const path = getPath();
    if (path === last) return;
    last = path;
    trackFunnel("pageview", { path });
    if (path === "/register") trackFunnel("signup_started", { path });
    if (path === "/walkthrough") trackFunnel("walkthrough_viewed", { path });
    if (path === "/billing") trackFunnel("upgrade_viewed", { path });
  };
  tick();
  // Poll is enough for this SPA (no history.listen without router hook).
  const id = window.setInterval(tick, 800);
  window.addEventListener("popstate", tick);
  return () => {
    window.clearInterval(id);
    window.removeEventListener("popstate", tick);
  };
}
