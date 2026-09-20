import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { formatApiError, smbApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { FormError } from "../components/FormError";

export function Login() {
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await smbApi.login(email.trim(), password);
      await refresh();
      navigate("/chat");
    } catch (err) {
      setError(
        formatApiError(err, "Incorrect email or password — try again."),
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
          <h1>Sign in</h1>
          <p className="muted">
            Sign in to the hosted advisory Q&amp;A example on this stack — or
            self-host the gateway from GitHub.
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
              required
              autoComplete="current-password"
            />
          </label>
          <FormError
            message={error}
            recovery="Double-check your email, or create a new account if you haven’t registered yet."
          />
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="muted small auth-footer-links">
          No account? <Link to="/register">Create one</Link>
          {" · "}
          <Link to="/onboarding">Continue as guest</Link>
        </p>
      </div>
    </section>
  );
}
