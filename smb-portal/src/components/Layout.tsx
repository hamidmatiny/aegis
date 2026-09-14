import { NavLink, Outlet, useLocation } from "react-router-dom";
import { clearGuestSession } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useGuestSession } from "../auth/useGuestSession";
import { BrandMark } from "./BrandMark";

const customerLinks = [
  { to: "/onboarding", label: "Setup" },
  { to: "/chat", label: "Q&A" },
  { to: "/walkthrough", label: "Walkthrough" },
  { to: "/billing", label: "Billing" },
];

/** Avatar-first surfaces own their chrome; don't wrap them in the sidebar shell. */
const ASSISTANT_PATHS = new Set(["/chat", "/walkthrough"]);

export function Layout() {
  const { me, usage, logout } = useAuth();
  const guest = useGuestSession();
  const location = useLocation();

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
  const assistantChrome = ASSISTANT_PATHS.has(location.pathname);

  if (!showSidebar) {
    return (
      <div className="app-shell marketing-shell">
        <header className="marketing-header">
          <BrandMark to="/" />
          <nav className="marketing-nav" aria-label="Primary">
            <a href="/#how-it-works">How it works</a>
            <a href="/#pricing">Pricing</a>
            <a
              href="https://github.com/hamidmatiny/aegis"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub
            </a>
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

  if (assistantChrome) {
    return (
      <div className="app-shell assistant-shell">
        <Outlet />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <BrandMark to="/chat" subtitle="SMB Copilot" />
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
