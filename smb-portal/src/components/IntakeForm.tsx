import { useState } from "react";
import type { FormEvent } from "react";
import type { IntakeAnswer } from "../api/types";

type FieldDef = {
  category: string;
  label: string;
  why: string;
  example: string;
  placeholder: string;
};

const FIELDS: FieldDef[] = [
  {
    category: "database",
    label: "Primary database",
    why: "We use this to match security advisories (CVEs) against the database software and version you actually run.",
    example: "PostgreSQL 16.2 on a managed RDS instance",
    placeholder: "e.g. PostgreSQL 16.2",
  },
  {
    category: "cloud",
    label: "Where your apps run",
    why: "Cloud provider and hosting shape which threats and hardening steps matter most for your setup.",
    example: "AWS with a few EC2 servers, or DigitalOcean droplets",
    placeholder: "e.g. AWS, Google Cloud, on-premise servers",
  },
  {
    category: "auth",
    label: "How people sign in",
    why: "Login and identity tools have their own CVE history — knowing yours helps us flag the right issues.",
    example: "Google Workspace for email, or Okta for staff logins",
    placeholder: "e.g. Google login, Microsoft 365, Okta",
  },
  {
    category: "messaging",
    label: "Queues or background jobs (optional)",
    why: "If you use message queues or job runners, we can include them in vulnerability checks too.",
    example: "Redis for caching, or nothing — skip if you don't use one",
    placeholder: "e.g. Redis, RabbitMQ — or leave blank",
  },
];

type Props = {
  busy?: boolean;
  onSubmit: (answers: IntakeAnswer[], skipped: string[]) => Promise<void>;
};

export function IntakeForm({ busy, onSubmit }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [skipped, setSkipped] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [submittedSkipped, setSubmittedSkipped] = useState<string[] | null>(null);

  function toggleSkip(category: string) {
    setSkipped((prev) => {
      const next = { ...prev, [category]: !prev[category] };
      if (next[category]) {
        setValues((v) => ({ ...v, [category]: "" }));
      }
      return next;
    });
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmittedSkipped(null);

    const skippedCategories = FIELDS.filter((f) => skipped[f.category]).map((f) => f.label);
    const answers: IntakeAnswer[] = FIELDS.filter(
      (f) => !skipped[f.category] && values[f.category]?.trim(),
    ).map((f) => ({
      category: f.category,
      value: values[f.category].trim(),
    }));

    if (answers.length === 0 && skippedCategories.length === 0) {
      setError('Answer at least one question, or choose "I\'m not sure" for fields you want to skip.');
      return;
    }

    try {
      await onSubmit(answers, skippedCategories);
      if (skippedCategories.length > 0) {
        setSubmittedSkipped(skippedCategories);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <form className="stack intake-form" onSubmit={handleSubmit}>
      {FIELDS.map((field) => {
        const isSkipped = skipped[field.category];
        return (
          <div key={field.category} className={`card intake-field${isSkipped ? " skipped" : ""}`}>
            <label className="field">
              <span className="field-label">{field.label}</span>
              <p className="field-help">{field.why}</p>
              <p className="field-example">
                <strong>Example:</strong> {field.example}
              </p>
              {!isSkipped ? (
                <input
                  value={values[field.category] ?? ""}
                  placeholder={field.placeholder}
                  onChange={(e) =>
                    setValues((prev) => ({ ...prev, [field.category]: e.target.value }))
                  }
                />
              ) : (
                <p className="skipped-note">Skipped — you can add this anytime from Settings.</p>
              )}
            </label>
            <button
              type="button"
              className="text-btn skip-btn"
              onClick={() => toggleSkip(field.category)}
            >
              {isSkipped ? "I'll answer this" : "I'm not sure — skip for now"}
            </button>
          </div>
        );
      })}

      {submittedSkipped && submittedSkipped.length > 0 ? (
        <div className="card skipped-summary" role="status">
          <h3>We don&apos;t have everything yet</h3>
          <p>That&apos;s okay — wrong guesses hurt CVE matching more than honest gaps.</p>
          <ul>
            {submittedSkipped.map((label) => (
              <li key={label}>
                We don&apos;t have your <strong>{label.toLowerCase()}</strong> yet — add it anytime
                from Settings.
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {error ? <p className="error">{error}</p> : null}
      <button type="submit" className="btn-primary" disabled={busy}>
        {busy ? "Saving…" : "Save and continue"}
      </button>
    </form>
  );
}
