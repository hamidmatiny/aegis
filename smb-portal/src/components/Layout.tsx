import { NavLink, Outlet } from "react-router-dom";
import { clearGuestSession, loadGuestSession } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const customerLinks = [
  { to: "/onboarding", label: "Onboarding" },
  { to: "/chat", label: "Q&A" },
  { to: "/walkthrough", label: "Walkthrough" },
  { to: "/billing", label: "Usage" },
];

export function Layout() {
  const { me, usage, logout } = useAuth();
  const guest = loadGuestSession();

  async function handleSignOut() {
    if (me?.role === "customer") {
      await logout();
      window.location.href = "/";
      return;
    }
    clearGuestSession();
    window.location.href = "/";
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand-block">
          <p className="brand">AEGIS SMB Portal</p>
          <p className="brand-tag">Infrastructure advisory for small teams</p>
        </div>
        {me?.role !== "admin" ? (
          <nav className="nav">
            {customerLinks.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        ) : null}
        <div className="session-chip">
          {me?.role === "customer" ? (
            <>
              <span className="badge">
                {me.tier} · {usage?.qa_ask_count ?? 0} Q&A
              </span>
              <span>
                <strong>{me.email}</strong>
              </span>
              <button type="button" className="linkish" onClick={handleSignOut}>
                Sign out
              </button>
            </>
          ) : guest ? (
            <>
              <span>
                Guest · tenant <strong>{guest.slug}</strong>
              </span>
              <button type="button" className="linkish" onClick={handleSignOut}>
                Clear guest session
              </button>
            </>
          ) : (
            <span>Guest — not signed in</span>
          )}
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
