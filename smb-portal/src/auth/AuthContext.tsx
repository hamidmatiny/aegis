import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { smbApi, type AuthMe } from "../api/client";
import type { UsageSummary } from "../api/types";

type AuthState = {
  me: AuthMe | null;
  loading: boolean;
  usage: UsageSummary | null;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<AuthMe | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const profile = await smbApi.me();
    setMe(profile);
    if (profile.role === "customer") {
      try {
        const summary = await smbApi.usage();
        setUsage(summary);
      } catch {
        setUsage(null);
      }
    } else {
      setUsage(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await refresh();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  const logout = useCallback(async () => {
    await smbApi.logout();
    setMe({ role: "guest" });
    setUsage(null);
  }, []);

  const value = useMemo(
    () => ({ me, loading, usage, refresh, logout }),
    [me, loading, usage, refresh, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
