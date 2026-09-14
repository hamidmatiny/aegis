type Props = {
  message: string | null;
  recovery?: string;
};

/** Styled auth/API error — clear copy near the form, never a raw JSON dump. */
export function FormError({ message, recovery }: Props) {
  if (!message) return null;
  return (
    <div className="form-error" role="alert">
      <p className="form-error-msg">{message}</p>
      {recovery ? <p className="form-error-hint">{recovery}</p> : null}
    </div>
  );
}
