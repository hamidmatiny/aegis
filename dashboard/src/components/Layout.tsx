import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/", label: "Attack Feed", end: true },
  { to: "/asr", label: "ASR Trends" },
  { to: "/policy", label: "Policy Editor" },
  { to: "/tools", label: "Tool Matrix" },
  { to: "/approvals", label: "Approvals" },
  { to: "/audit", label: "Audit Log" },
];

export function Layout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          AEG<span>IS</span>
        </div>
        <nav>
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
