import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { saveGuestSession, smbApi } from "../api/client";
import type { IntakeAnswer } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useGuestSession } from "../auth/useGuestSession";
import { IntakeForm } from "../components/IntakeForm";

export function Onboarding() {
  const navigate = useNavigate();
  const { me } = useAuth();
  const guest = useGuestSession();
  const isCustomer = me?.role === "customer";

  const [slug, setSlug] = useState("");
  const [apiKeyOnce, setApiKeyOnce] = useState<string | null>(null);
  // Layout remounts Outlet when guest session appears (marketing → sidebar).
  // Re-hydrate registered from guest session so intake survives that remount.
  const [registered, setRegistered] = useState(() => isCustomer || Boolean(guest));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profileSaved, setProfileSaved] = useState(false);

  async function handleRegister(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const cleaned = slug.trim().toLowerCase();
      const resp = await smbApi.register(cleaned);
      saveGuestSession({
        apiKey: resp.api_key,
        tenantId: resp.tenant_id,
        slug: resp.slug,
      });
      setApiKeyOnce(resp.api_key);
      setRegistered(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleIntake(answers: IntakeAnswer[], _skipped: string[]) {
    setBusy(true);
    setError(null);
    try {
      if (answers.length > 0) {
        await smbApi.intake(answers);
      }
      setProfileSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      throw err;
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <header className="page-header">
        <h1>{isCustomer ? "Describe your infrastructure" : "Try the Q&A example as a guest"}</h1>
        <p className="page-subtitle">
          {isCustomer
            ? "A short inventory so the hosted advisory Q&A (an applied example on the AEGIS gateway stack) can ground answers in what you actually run — not a product pitch for autonomous action."
            : "Try the hosted advisory Q&A without an account. Temporary workspace stays in this browser only. The open-source enforcer/gateway is separate on GitHub."}
        </p>
      </header>

      {!registered ? (
        <div className="card">
          <h2 className="card-title">Choose a workspace name</h2>
          <p className="card-desc">
            A short label for this trial workspace. Use lowercase letters, numbers,
            and hyphens only.
          </p>
          <form className="stack form" onSubmit={handleRegister}>
            <label className="field">
              <span>Workspace name</span>
              <input
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="acme-ops"
                pattern="^[a-z0-9][a-z0-9\-]*$"
                minLength={2}
                maxLength={64}
                required
              />
              <p className="field-example">
                <strong>Example:</strong> staging-lab or prod-inventory
              </p>
            </label>
            {error ? <p className="error">{error}</p> : null}
            <button type="submit" className="btn-primary" disabled={busy || !slug.trim()}>
              {busy ? "Creating workspace…" : "Continue as guest"}
            </button>
          </form>
          <p className="muted small">
            Want a permanent account? <Link to="/register">Sign up with email</Link> instead.
          </p>
        </div>
      ) : (
        <>
          {apiKeyOnce ? (
            <div className="card warn-card">
              <h2 className="card-title">Your guest access key (shown once)</h2>
              <p className="card-desc">
                This key stays in this browser so you can keep using Q&A. Copy it now if you
                might need it on another device.
              </p>
              <p className="mono key-display">{apiKeyOnce}</p>
            </div>
          ) : null}

          <div className="card">
            <h2 className="card-title">What does this environment run on?</h2>
            <p className="card-desc">
              Databases, hosting, and auth so advisory answers and CVE matches
              ground in your inventory — not a generic checklist. Answers stay
              advisory; nothing here changes your systems.
            </p>
            <IntakeForm busy={busy} onSubmit={handleIntake} />
            {profileSaved ? (
              <div className="success-banner">
                <p>
                  Profile saved.{" "}
                  <button type="button" className="text-btn" onClick={() => navigate("/chat")}>
                    Go to Q&A →
                  </button>
                </p>
              </div>
            ) : null}
            {error ? <p className="error">{error}</p> : null}
          </div>
        </>
      )}
    </section>
  );
}
