import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { smbApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";

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
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <header className="page-hero">
        <h1>Create account</h1>
        <p>Register with email and password. You can complete infra intake next.</p>
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
            />
          </label>
          <label className="field">
            <span>Tenant slug (optional)</span>
            <input
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="acme-smb"
              pattern="^[a-z0-9][a-z0-9\-]*$"
            />
          </label>
          {error ? <p className="error">{error}</p> : null}
          <button type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create account"}
          </button>
        </form>
        <p className="muted">
          Already registered? <Link to="/login">Sign in</Link>.
        </p>
      </div>
    </section>
  );
}
