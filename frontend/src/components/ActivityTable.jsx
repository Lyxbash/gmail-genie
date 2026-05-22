import CategoryBadge from "./CategoryBadge";
import EmptyState from "./EmptyState";
import { confidenceBand } from "../utils/userLabels";

function formatTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function sourceLabel(source, developerMode) {
  if (!developerMode) {
    const s = (source || "").toLowerCase();
    if (s.includes("groq") || s.includes("semantic") || s.includes("verify")) {
      return "AI reviewed";
    }
    return "Rules";
  }
  return source || "rules";
}

export default function ActivityTable({ items = [], developerMode = false }) {
  if (!items.length) {
    return (
      <EmptyState
        title="No activity yet"
        message="Organize recent mail from the dashboard — your history will show up here."
      />
    );
  }

  return (
    <div className="table-scroll-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Sender</th>
            <th>Subject</th>
            <th>Category</th>
            <th>Confidence</th>
            {developerMode ? <th>Source</th> : null}
            <th>Label applied</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row, i) => {
            const band = confidenceBand(row.confidence);
            return (
              <tr key={row.message_id || `${row.sender}-${i}`}>
                <td className="truncate" title={row.sender}>
                  {row.sender || "—"}
                </td>
                <td className="truncate" title={row.subject}>
                  {row.subject || "—"}
                </td>
                <td>
                  <CategoryBadge category={row.category} />
                </td>
                <td>
                  <span className={`confidence-pill ${band.level}`}>{band.label}</span>
                </td>
                {developerMode ? (
                  <td className="dev-cell">
                    <code>{row.source || "rules"}</code>
                  </td>
                ) : null}
                <td>{row.action_applied ? "Yes" : "No"}</td>
                <td>{formatTime(row.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
