import { useMemo, useSyncExternalStore } from "react";
import {
  getGuestSessionSnapshot,
  loadGuestSession,
  subscribeGuestSession,
  type GuestSession,
} from "../api/client";

/** Reactive guest session — re-renders when saveGuestSession/clearGuestSession run. */
export function useGuestSession(): GuestSession | null {
  const snapshot = useSyncExternalStore(
    subscribeGuestSession,
    getGuestSessionSnapshot,
    () => "",
  );
  // snapshot is the external-store signal; loadGuestSession reads sessionStorage.
  // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional: re-parse when snapshot changes
  return useMemo(() => loadGuestSession(), [snapshot]);
}
