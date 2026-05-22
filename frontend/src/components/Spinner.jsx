export default function Spinner({ size = 14, className = "" }) {
  return (
    <span
      className={`spinner-inline ${className}`.trim()}
      style={{
        width: size,
        height: size,
        borderWidth: Math.max(2, Math.floor(size / 7)),
      }}
      aria-hidden
    />
  );
}
