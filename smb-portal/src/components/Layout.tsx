import { NavLink, Outlet } from "react-router-dom";
import { clearSession, loadSession } from "../api/client";

const links = [
  { to: "/onboarding", label: "Onboarding" },
  { to: "/chat", label: "Q&A" },
  { to: "/walkthrough", label: "Walkthrough" },
  { to: "/billing", label: "Usage" },
];

export function Layout() {
  const session = loadSession();

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand-block">
          <p className="brand">AEGIS SMB Portal</p>
          <p className="brand-tag">Infrastructure advisory for small teams</p>
        </div>
        <nav className="nav">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="session-chip">
          {session ? (
            <>
              <span>
                Tenant <strong>{session.slug}</strong>
              </span>
              <button
                type="button"
                className="linkish"
                onClick={() => {
                  clearSession();
                  window.location.href = "/onboarding";
                }}
              >
                Sign out
              </button>
            </>
          ) : (
            <span>Not registered</span>
          )}
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
