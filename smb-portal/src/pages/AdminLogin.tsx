import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { smbApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function AdminLogin() {
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await smbApi.adminLogin(username.trim(), password);
      await refresh();
      navigate("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <header className="page-hero">
        <h1>Operator sign in</h1>
        <p>Admin access for tenant management and tier control.</p>
      </header>
      <div className="panel">
        <form className="stack form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Username</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
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
            {busy ? "Signing in…" : "Sign in as operator"}
          </button>
        </form>
      </div>
    </section>
  );
}
