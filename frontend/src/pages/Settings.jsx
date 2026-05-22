import { useEffect, useState } from "react";
import { getConfigSummary, getHealth } from "../api/client";
import HealthIndicator from "../components/HealthIndicator";

export default function Settings() {
  const [config, setConfig] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([getConfigSummary(), getHealth()])
      .then(([cfg, h]) => {
        setConfig(cfg);
        setHealth(h);
      })
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return <div className="alert alert-error">{error}</div>;
  }

  if (!config) {
    return <div className="loading">Loading settings…</div>;
  }

  const t = config.thresholds || {};
  const limits = config.limits || {};
  const features = config.features || {};

  return (
    <div>
      <header className="page-header">
        <h1>Settings</h1>
        <p className="text-muted">
          Read-only config · labels only · inbox never archived automatically
        </p>
      </header>

      <div className="card">
        <h2>System health</h2>
        <div className="health-row">
          <HealthIndicator label="Gmail" ok={health?.gmail_connected} />
          <HealthIndicator label="Ollama" ok={health?.ollama_available} warn />
          <HealthIndicator label="Groq" ok={health?.groq_enabled} warn />
          <HealthIndicator label="Database" ok={health?.database_ok} />
        </div>
      </div>

      <div className="config-grid">
        <div className="card">
          <h2>LLM provider</h2>
          <dl>
            <dt>Provider</dt>
            <dd>{config.provider}</dd>
            <dt>Model</dt>
            <dd>{config.model || "—"}</dd>
          </dl>
        </div>

        <div className="card">
          <h2>Thresholds</h2>
          <dl>
            {Object.entries(t).map(([k, v]) => (
              <div key={k}>
                <dt>{k.replace(/_/g, " ")}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="card">
          <h2>Limits</h2>
          <dl>
            {Object.entries(limits).map(([k, v]) => (
              <div key={k}>
                <dt>{k.replace(/_/g, " ")}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="card">
          <h2>Features</h2>
          <dl>
            {Object.entries(features).map(([k, v]) => (
              <div key={k}>
                <dt>{k.replace(/_/g, " ")}</dt>
                <dd>{v ? "Enabled" : "Disabled"}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="card">
          <h2>Categories ({config.categories?.length || 0})</h2>
          <p style={{ fontSize: "0.8rem", color: "#8b9cb3", margin: 0 }}>
            {config.categories?.join(", ")}
          </p>
        </div>
      </div>

      <div className="alert alert-info">
        Safe mode: dry-run is recommended for testing. Review queue + corrections
        improve rules without retraining.
      </div>
    </div>
  );
}
