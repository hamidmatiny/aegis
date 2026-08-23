import { Link } from "react-router-dom";
import { loadSession } from "../api/client";
import { ChatPanel } from "../components/ChatPanel";

export function QAChat() {
  const session = loadSession();

  if (!session) {
    return (
      <section className="page">
        <header className="page-hero">
          <h1>Q&A</h1>
          <p>
            Register a tenant first. <Link to="/onboarding">Start onboarding</Link>
          </p>
        </header>
      </section>
    );
  }

  return (
    <section className="page">
      <header className="page-hero">
        <h1>Advisory Q&A</h1>
        <p>
          Free-tier answers grounded in your infra profile. Disclaimers render
          with every answer and cannot be dismissed.
        </p>
      </header>
      <div className="panel">
        <ChatPanel />
      </div>
    </section>
  );
}
