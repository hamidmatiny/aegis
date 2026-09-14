type Props = {
  /** Path under site root, e.g. `/assistant/aegis-robot.png` — swappable later. */
  src?: string;
  alt?: string;
  listening?: boolean;
  className?: string;
};

/**
 * Swappable assistant figure. Ambient rings/halo animate; the image itself stays still.
 */
export function AegisAvatar({
  src = "/assistant/aegis-robot.png",
  alt = "AEGIS assistant",
  listening = false,
  className = "",
}: Props) {
  return (
    <div className={`avatar-wrap ${className}`.trim()} aria-hidden={false}>
      <div className={`halo${listening ? " listening" : ""}`} />
      <div className="ring r1" />
      <div className="ring r2" />
      <img
        className={`figure-img${listening ? " listening" : ""}`}
        src={src}
        alt={alt}
        width={135}
        height={180}
        draggable={false}
      />
    </div>
  );
}
