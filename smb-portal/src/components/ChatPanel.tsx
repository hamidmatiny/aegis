import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { smbApi } from "../api/client";
import type { AskAnswer } from "../api/types";

type ChatTurn = {
  id: string;
  question: string;
  answer: AskAnswer;
};

type Props = {
  walkthroughMode?: boolean;
};

export function ChatPanel({ walkthroughMode = false }: Props) {
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await smbApi.ask(text, walkthroughMode);
      if (resp.type === "upsell") {
        navigate("/walkthrough", {
          state: {
            message: resp.message,
            question: text,
          },
        });
        return;
      }
      setTurns((prev) => [
        ...prev,
        { id: `${Date.now()}`, question: text, answer: resp },
      ]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat">
      <div className="chat-log">
        {turns.length === 0 ? (
          <p className="muted">
            Ask an infrastructure question
            {walkthroughMode ? " for a guided walkthrough" : ""}. Each answer
            includes a mandatory advisory disclaimer.
          </p>
        ) : null}
        {turns.map((turn) => (
          <article key={turn.id} className="chat-turn">
            <div className="bubble user">
              <p className="bubble-label">You</p>
              <p>{turn.question}</p>
            </div>
            <div className="bubble assistant">
              <p className="bubble-label">
                AEGIS{turn.answer.walkthrough ? " · Walkthrough" : ""}
              </p>
              <p className="answer-text">{turn.answer.answer}</p>
              {turn.answer.cve_matches.length > 0 ? (
                <ul className="cve-list">
                  {turn.answer.cve_matches.map((cve) => (
                    <li key={`${cve.cve_id}-${cve.matched_value}`}>
                      <strong>{cve.cve_id}</strong> [{cve.severity}] on{" "}
                      {cve.matched_value}: {cve.summary}
                    </li>
                  ))}
                </ul>
              ) : null}
              <aside className="disclaimer" role="note" aria-label="Advisory disclaimer">
                <strong>Advisory disclaimer</strong>
                <p>{turn.answer.disclaimer}</p>
              </aside>
            </div>
          </article>
        ))}
      </div>
      <form className="composer" onSubmit={handleSubmit}>
        <textarea
          rows={3}
          value={question}
          placeholder={
            walkthroughMode
              ? "Describe what you want a step-by-step walkthrough for…"
              : "e.g. How should we harden our Postgres 16.2 deployment?"
          }
          onChange={(e) => setQuestion(e.target.value)}
          disabled={busy}
        />
        {error ? <p className="error">{error}</p> : null}
        <div className="composer-actions">
          <button type="submit" disabled={busy || !question.trim()}>
            {busy ? "Thinking…" : walkthroughMode ? "Request walkthrough" : "Ask"}
          </button>
        </div>
      </form>
    </div>
  );
}
