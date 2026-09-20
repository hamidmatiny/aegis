import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { formatApiError, smbApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { FormError } from "../components/FormError";

export function Register() {
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [slug, setSlug] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await smbApi.registerAccount(
        email.trim(),
        password,
        slug.trim() || undefined,
      );
      await refresh();
      navigate("/onboarding");
    } catch (err) {
      setError(
        formatApiError(
          err,
          "Could not create your account — try a different email or try again.",
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="auth-page">
      <div className="auth-card card">
        <header className="auth-card-head">
          <p className="landing-kicker">LLM security gateway</p>
          <h1>Create account</h1>
          <p className="muted">
            Free to try the hosted advisory Q&amp;A example. You can describe
            your infrastructure next — the open-source gateway stays on GitHub.
          </p>
        </header>
        <form className="stack form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
              autoComplete="new-password"
            />
          </label>
          <label className="field">
            <span>Workspace name (optional)</span>
            <input
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="acme-ops"
              pattern="^[a-z0-9][a-z0-9\-]*$"
            />
            <p className="field-example">
              Lowercase letters, numbers, and hyphens only.
            </p>
          </label>
          <FormError message={error} />
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Creating…" : "Create account"}
          </button>
        </form>
        <p className="muted small auth-footer-links">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </section>
  );
}
