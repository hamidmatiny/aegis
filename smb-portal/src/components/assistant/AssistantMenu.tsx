import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useGuestSession } from "../../auth/useGuestSession";

type Props = {
  onJumpToHistory?: () => void;
};

export function AssistantMenu({ onJumpToHistory }: Props) {
  const { me, logout } = useAuth();
  const guest = useGuestSession();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, []);

  async function handleSignOut() {
    setOpen(false);
    await logout();
    window.location.href = "/";
  }

  const label =
    me?.role === "customer"
      ? me.email
      : guest
        ? `Guest · ${guest.slug}`
        : "Account";

  return (
    <div className="menu-btn-wrap" ref={rootRef}>
      <button
        type="button"
        className="menu-btn"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="12" cy="7" r="4" />
          <path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" />
        </svg>
      </button>
      {open ? (
        <div className="menu-panel open" role="menu">
          <p className="menu-panel-label muted small">{label}</p>
          <Link role="menuitem" to="/onboarding" onClick={() => setOpen(false)}>
            Setup / inventory
          </Link>
          <Link role="menuitem" to="/billing" onClick={() => setOpen(false)}>
            Billing
          </Link>
          <Link role="menuitem" to="/walkthrough" onClick={() => setOpen(false)}>
            Guided walkthroughs
          </Link>
          {onJumpToHistory ? (
            <button
              type="button"
              role="menuitem"
              className="menu-panel-btn"
              onClick={() => {
                setOpen(false);
                onJumpToHistory();
              }}
            >
              Past conversations
            </button>
          ) : (
            <button
              type="button"
              role="menuitem"
              className="menu-panel-btn"
              onClick={() => {
                setOpen(false);
                navigate("/chat#history");
              }}
            >
              Past conversations
            </button>
          )}
          <button
            type="button"
            role="menuitem"
            className="menu-panel-btn menu-panel-danger"
            onClick={handleSignOut}
          >
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
