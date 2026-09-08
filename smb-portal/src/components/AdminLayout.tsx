import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { BrandMark } from "./BrandMark";

const adminLinks = [
  { to: "/admin", label: "Tenants", end: true },
  { to: "/admin/engine-demo", label: "Engine demo", end: false },
];

export function AdminLayout() {
  const { logout } = useAuth();

  async function handleSignOut() {
    await logout();
    window.location.href = "/";
  }

  return (
    <div className="app-shell admin-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <BrandMark to="/admin" subtitle="Operator console" />
        </div>
        <nav className="sidebar-nav">
          {adminLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button type="button" className="text-btn" onClick={handleSignOut}>
            Sign out
          </button>
        </div>
      </aside>
      <div className="main-column">
        <header className="top-strip">
          <span className="muted small">Admin-only · internal showcase</span>
        </header>
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
