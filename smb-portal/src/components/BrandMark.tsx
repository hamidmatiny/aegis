import { NavLink } from "react-router-dom";

type Props = {
  to?: string;
  subtitle?: string;
  className?: string;
};

/** Shared AEGIS wordmark + shield logo (same asset as demo-web). */
export function BrandMark({ to = "/", subtitle, className = "" }: Props) {
  const inner = (
    <>
      <img src="/icon.svg" alt="" width={28} height={28} className="brand-logo" />
      <span className="brand-text">
        <span className="brand-word">AEGIS</span>
        {subtitle ? <span className="brand-sub">{subtitle}</span> : null}
      </span>
    </>
  );

  if (to) {
    return (
      <NavLink to={to} className={`brand-mark ${className}`.trim()}>
        {inner}
      </NavLink>
    );
  }
  return <div className={`brand-mark ${className}`.trim()}>{inner}</div>;
}
