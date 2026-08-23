import { useState } from "react";
import type { FormEvent } from "react";
import type { IntakeAnswer } from "../api/types";

const FIELDS: Array<{ category: string; label: string; placeholder: string }> = [
  {
    category: "database",
    label: "Primary database",
    placeholder: "e.g. PostgreSQL 16.2",
  },
  {
    category: "cloud",
    label: "Cloud / orchestrator",
    placeholder: "e.g. AWS EKS",
  },
  {
    category: "auth",
    label: "Auth / identity",
    placeholder: "e.g. Auth0, Cognito",
  },
  {
    category: "messaging",
    label: "Messaging / queue",
    placeholder: "e.g. Redis, SQS (optional)",
  },
];

type Props = {
  busy?: boolean;
  onSubmit: (answers: IntakeAnswer[]) => Promise<void>;
};

export function IntakeForm({ busy, onSubmit }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const answers: IntakeAnswer[] = FIELDS.filter((f) => values[f.category]?.trim()).map(
      (f) => ({
        category: f.category,
        value: values[f.category].trim(),
      }),
    );
    if (answers.length === 0) {
      setError("Add at least one infrastructure answer.");
      return;
    }
    try {
      await onSubmit(answers);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <form className="stack form" onSubmit={handleSubmit}>
      {FIELDS.map((field) => (
        <label key={field.category} className="field">
          <span>{field.label}</span>
          <input
            value={values[field.category] ?? ""}
            placeholder={field.placeholder}
            onChange={(e) =>
              setValues((prev) => ({ ...prev, [field.category]: e.target.value }))
            }
          />
        </label>
      ))}
      {error ? <p className="error">{error}</p> : null}
      <button type="submit" disabled={busy}>
        {busy ? "Saving…" : "Save infrastructure profile"}
      </button>
    </form>
  );
}
