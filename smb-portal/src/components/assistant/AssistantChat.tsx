import { useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { formatApiError, smbApi } from "../../api/client";
import type { AskAnswer } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { FormError } from "../FormError";
import { AegisAvatar } from "./AegisAvatar";
import { AssistantComposer, isSignOutIntent } from "./AssistantComposer";
import { AssistantMenu } from "./AssistantMenu";

type ChatTurn = {
  id: string;
  question: string;
  answer: AskAnswer;
  at: number;
};

type Props = {
  walkthroughMode?: boolean;
};

function dayLabel(ts: number): string {
  const d = new Date(ts);
  const today = new Date();
  const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  const startThat = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diffDays = Math.round((startToday - startThat) / 86400000);
  if (diffDays === 0) return "Earlier today";
  if (diffDays === 1) return "Yesterday";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function AssistantChat({ walkthroughMode = false }: Props) {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const historyRef = useRef<HTMLDivElement>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [listeningUi, setListeningUi] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);

  const grouped = useMemo(() => {
    const map = new Map<string, ChatTurn[]>();
    for (const turn of turns) {
      const key = dayLabel(turn.at);
      const list = map.get(key) ?? [];
      list.push(turn);
      map.set(key, list);
    }
    return [...map.entries()];
  }, [turns]);

  function jumpToHistory() {
    historyRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function signOutFully() {
    await logout();
    window.location.href = "/";
  }

  async function sendQuestion() {
    const text = question.trim();
    if (!text || busy) return;

    if (isSignOutIntent(text)) {
      setQuestion("");
      await signOutFully();
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const resp = await smbApi.ask(text, walkthroughMode);
      if (resp.type === "upsell") {
        navigate("/walkthrough", {
          state: { message: resp.message, question: text },
        });
        return;
      }
      setTurns((prev) => [
        ...prev,
        { id: `${Date.now()}`, question: text, answer: resp, at: Date.now() },
      ]);
      setQuestion("");
    } catch (err) {
      setError(formatApiError(err, "Could not get an answer — try again in a moment."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="assistant-page">
      <div className="assistant-hero">
        <header className="assistant-nav">
          <Link to="/chat" className="assistant-brand">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M12 2l8 3v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V5l8-3z" />
            </svg>
            AEGIS
          </Link>
          <AssistantMenu onJumpToHistory={jumpToHistory} />
        </header>

        <AegisAvatar listening={listeningUi || busy} />

        <p className="status-line">
          <span className="status-dot" aria-hidden="true" />
          <span>
            {busy
              ? "Thinking…"
              : listeningUi
                ? "Listening…"
                : walkthroughMode
                  ? "Ready for a guided walkthrough"
                  : "Listening for your question"}
          </span>
        </p>

        <AssistantComposer
          value={question}
          onChange={setQuestion}
          onSubmit={() => void sendQuestion()}
          busy={busy}
          onListeningChange={setListeningUi}
          placeholder={
            walkthroughMode
              ? "Describe what you want a step-by-step walkthrough for…"
              : 'Ask about your stack, or say "sign me out"…'
          }
        />

        <FormError message={error} />

        {turns.length > 0 ? (
          <button type="button" className="scroll-hint" onClick={jumpToHistory}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M12 5v14M5 12l7 7 7-7" />
            </svg>
            scroll for history
          </button>
        ) : (
          <p className="scroll-hint muted">Ask in plain English — answers stay advisory-only.</p>
        )}
      </div>

      <div className="assistant-history" id="history" ref={historyRef}>
        {turns.length === 0 ? (
          <p className="muted history-empty">
            Conversation history appears here after you ask. CVE matches and the advisory
            disclaimer stay attached to every answer.
          </p>
        ) : (
          grouped.map(([label, items]) => (
            <section key={label}>
              <h2 className="history-label">{label}</h2>
              {items.map((turn) => (
                <article key={turn.id} className="exchange">
                  <div className="bubble user">
                    <p>{turn.question}</p>
                  </div>
                  <div className="bubble ai">
                    <p className="bubble-meta">
                      AEGIS{turn.answer.walkthrough ? " · Walkthrough" : ""}
                    </p>
                    <p className="answer-text">{turn.answer.answer}</p>
                    {turn.answer.cve_matches.length > 0 ? (
                      <ul className="cve-cite-list">
                        {turn.answer.cve_matches.map((cve) => (
                          <li key={`${cve.cve_id}-${cve.matched_value}`}>
                            <span className="cite">
                              {cve.cve_id} · {cve.severity}
                            </span>{" "}
                            <span className="muted small">
                              on {cve.matched_value}: {cve.summary}
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    <aside className="disclaimer" role="note">
                      <strong>Advisory disclaimer</strong>
                      <p>{turn.answer.disclaimer}</p>
                    </aside>
                  </div>
                </article>
              ))}
            </section>
          ))
        )}
      </div>
    </div>
  );
}
