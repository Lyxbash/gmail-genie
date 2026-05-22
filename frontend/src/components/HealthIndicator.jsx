export default function HealthIndicator({ label, ok, warn }) {
  let status = "err";
  if (ok) status = "ok";
  else if (warn) status = "warn";

  const text =
    status === "ok" ? "OK" : status === "warn" ? "Degraded" : "Down";

  return (
    <div className="health-indicator">
      <span className={`health-dot ${status}`} />
      <span>
        {label}: <strong>{text}</strong>
      </span>
    </div>
  );
}
