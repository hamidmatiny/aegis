import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { saveSession, smbApi } from "../api/client";
import type { IntakeAnswer } from "../api/types";
import { IntakeForm } from "../components/IntakeForm";

export function Onboarding() {
  const navigate = useNavigate();
  const [slug, setSlug] = useState("");
  const [apiKeyOnce, setApiKeyOnce] = useState<string | null>(null);
  const [registered, setRegistered] = useState(false);
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
      saveSession({
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

  async function handleIntake(answers: IntakeAnswer[]) {
    setBusy(true);
    setError(null);
    try {
      await smbApi.intake(answers);
      setProfileSaved(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <header className="page-hero">
        <h1>Onboarding</h1>
        <p>
          Register a tenant, store the API key once, then capture a normalized
          infrastructure profile for advisory Q&A.
        </p>
      </header>

      {!registered ? (
        <div className="panel">
          <h2>Create tenant</h2>
          <form className="stack form" onSubmit={handleRegister}>
            <label className="field">
              <span>Slug</span>
              <input
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="acme-smb"
                pattern="^[a-z0-9][a-z0-9\-]*$"
                minLength={2}
                maxLength={64}
                required
              />
            </label>
            {error ? <p className="error">{error}</p> : null}
            <button type="submit" disabled={busy || !slug.trim()}>
              {busy ? "Registering…" : "Register"}
            </button>
          </form>
        </div>
      ) : (
        <>
          {apiKeyOnce ? (
            <div className="panel warn-panel">
              <h2>API key (shown once)</h2>
              <p className="mono">{apiKeyOnce}</p>
              <p className="muted">
                Stored in this browser session for portal calls. Copy it now if
                you need it elsewhere.
              </p>
            </div>
          ) : null}

          <div className="panel">
            <h2>Infrastructure intake</h2>
            <IntakeForm busy={busy} onSubmit={handleIntake} />
            {profileSaved ? (
              <p className="ok">
                Profile saved.{" "}
                <Link to="/chat">Continue to Q&A</Link> or{" "}
                <button type="button" className="linkish" onClick={() => navigate("/chat")}>
                  open chat
                </button>
                .
              </p>
            ) : null}
            {error ? <p className="error">{error}</p> : null}
          </div>
        </>
      )}
    </section>
  );
}
