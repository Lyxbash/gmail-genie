import { useEffect, useState } from "react";
import { getConfigSummary } from "../api/client";

export default function LabelSetupNotice({ compact = false }) {
  const [labels, setLabels] = useState([]);

  useEffect(() => {
    getConfigSummary()
      .then((cfg) => setLabels(cfg.label_paths || []))
      .catch(() => setLabels([]));
  }, []);

  if (!labels.length) return null;

  if (compact) {
    return (
      <p className="text-muted label-setup-compact">
        Gmail labels will be created under paths like{" "}
        <strong>{labels.slice(0, 3).join(", ")}</strong>
        {labels.length > 3 ? ` (+${labels.length - 3} more)` : ""}. Your inbox
        is never archived.
      </p>
    );
  }

  return (
    <div className="label-setup-notice">
      <h4>Gmail labels Genie will use</h4>
      <p className="text-muted">
        On first apply, these label folders are created in Gmail if they do not
        exist yet. Only labels are added — mail stays in your inbox.
      </p>
      <ul className="label-setup-list">
        {labels.map((name) => (
          <li key={name}>{name}</li>
        ))}
      </ul>
    </div>
  );
}
