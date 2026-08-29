import { NavLink, Outlet } from "react-router-dom";
import { clearGuestSession, loadGuestSession } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const customerLinks = [
  { to: "/onboarding", label: "Setup" },
  { to: "/chat", label: "Q&A" },
  { to: "/walkthrough", label: "Walkthrough" },
  { to: "/billing", label: "Billing" },
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

  const showSidebar = me?.role === "customer" || guest;

  if (!showSidebar) {
    return (
      <div className="app-shell marketing-shell">
        <header className="marketing-header">
          <NavLink to="/" className="brand-mark">
            AEGIS
          </NavLink>
          <nav className="marketing-nav">
            <NavLink to="/login">Sign in</NavLink>
            <NavLink to="/register" className="btn-primary btn-sm">
              Sign up
            </NavLink>
          </nav>
        </header>
        <main className="page-content marketing-content">
          <Outlet />
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <NavLink to="/chat" className="brand-mark">
            AEGIS
          </NavLink>
          <p className="brand-sub">SMB Copilot</p>
        </div>
        <nav className="sidebar-nav">
          {customerLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          {me?.role === "customer" ? (
            <>
              <p className="sidebar-user">
                <span className="plan-pill">{me.tier}</span>
                <span className="truncate">{me.email}</span>
              </p>
              <p className="muted small">{usage?.qa_ask_count ?? 0} Q&A this period</p>
            </>
          ) : guest ? (
            <p className="sidebar-user">
              Guest · <strong>{guest.slug}</strong>
            </p>
          ) : null}
          <button type="button" className="text-btn" onClick={handleSignOut}>
            Sign out
          </button>
        </div>
      </aside>
      <div className="main-column">
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
