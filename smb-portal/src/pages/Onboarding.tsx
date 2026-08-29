import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { saveGuestSession, smbApi } from "../api/client";
import type { IntakeAnswer } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { IntakeForm } from "../components/IntakeForm";

export function Onboarding() {
  const navigate = useNavigate();
  const { me } = useAuth();
  const isCustomer = me?.role === "customer";

  const [slug, setSlug] = useState("");
  const [apiKeyOnce, setApiKeyOnce] = useState<string | null>(null);
  const [registered, setRegistered] = useState(isCustomer);
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
        <h1>{isCustomer ? "Tell us about your setup" : "Get started as a guest"}</h1>
        <p className="page-subtitle">
          {isCustomer
            ? "A few quick questions about what you run today. No technical jargon required — honest answers (or “I'm not sure”) help us give better guidance."
            : "Try AEGIS without creating an account. You'll get a temporary workspace in this browser only."}
        </p>
      </header>

      {!registered ? (
        <div className="card">
          <h2 className="card-title">Choose a workspace name</h2>
          <p className="card-desc">
            This is just a short label for your trial — like a nickname for your business.
            Use lowercase letters, numbers, and hyphens only.
          </p>
          <form className="stack form" onSubmit={handleRegister}>
            <label className="field">
              <span>Workspace name</span>
              <input
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="acme-bakery"
                pattern="^[a-z0-9][a-z0-9\-]*$"
                minLength={2}
                maxLength={64}
                required
              />
              <p className="field-example">
                <strong>Example:</strong> joes-plumbing or main-street-cafe
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
            <h2 className="card-title">What does your business run on?</h2>
            <p className="card-desc">
              We ask about databases, hosting, and logins so answers and CVE alerts match
              your real environment — not a generic checklist.
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
