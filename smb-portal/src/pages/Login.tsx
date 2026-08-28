import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { smbApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";

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
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <header className="page-hero">
        <h1>Customer sign in</h1>
        <p>Use the email and password from your SMB Copilot account.</p>
      </header>
      <div className="panel">
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
          {error ? <p className="error">{error}</p> : null}
          <button type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="muted">
          No account?{" "}
          <Link to="/register">Create one</Link> or{" "}
          <Link to="/onboarding">continue as guest</Link>.
        </p>
      </div>
    </section>
  );
}
