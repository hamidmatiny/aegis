import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useGuestSession } from "./useGuestSession";

export function CustomerGuard() {
  const { me, loading } = useAuth();
  const guest = useGuestSession();

  if (loading) {
    return <p className="muted page-pad">Loading session…</p>;
  }
  if (me?.role === "admin") {
    return <Navigate to="/admin" replace />;
  }
  if (me?.role === "customer" || guest) {
    return <Outlet />;
  }
  return <Navigate to="/login" replace />;
}

export function AdminGuard() {
  const { me, loading } = useAuth();

  if (loading) {
    return <p className="muted page-pad">Loading session…</p>;
  }
  if (me?.role === "admin") {
    return <Outlet />;
  }
  return <Navigate to="/admin/login" replace />;
}

export function GuestOnly({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <p className="muted page-pad">Loading…</p>;
  if (me?.role === "admin") {
    return <Navigate to="/admin" replace />;
  }
  if (me?.role === "customer") {
    return <Navigate to="/chat" replace />;
  }
  return <>{children}</>;
}
