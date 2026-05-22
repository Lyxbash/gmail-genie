import { useEffect, useState } from "react";
import { getOnboardingStatus } from "../api/client";

export default function OnboardingChecklist() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const st = await getOnboardingStatus();
        if (mounted) {
          setData(st);
          setError(null);
        }
      } catch (err) {
        if (mounted) setError(err.message || "Could not load setup status");
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  if (error) {
    return (
      <div className="card onboarding-card">
        <h2>Setup checklist</h2>
        <p className="text-muted">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="card onboarding-card">
        <h2>Setup checklist</h2>
        <p className="text-muted">Checking local setup…</p>
      </div>
    );
  }

  const items = data.items || [];
  const ready = data.ready;

  return (
    <div className="card onboarding-card">
      <div className="onboarding-header">
        <h2>Setup checklist</h2>
        <span className={`setup-badge ${ready ? "ok" : "pending"}`}>
          {ready ? "Ready to organize" : "Finish setup below"}
        </span>
      </div>
      <p className="text-muted" style={{ marginTop: 0 }}>
        {data.privacy_note ||
          "Your email is processed on this machine — Gmail API is the only external connection."}
      </p>
      <ul className="onboarding-list">
        {items.map((item) => (
          <li key={item.id} className={item.ok ? "ok" : "pending"}>
            <span className="check-icon">{item.ok ? "✓" : "○"}</span>
            <span className="check-label">{item.label}</span>
            {!item.ok && item.hint ? (
              <span className="check-hint">{item.hint}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
