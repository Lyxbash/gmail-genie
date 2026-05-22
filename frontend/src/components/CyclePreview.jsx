import { useMemo, useState } from "react";
import CategoryBadge from "./CategoryBadge";

export default function CyclePreview({ preview, report, dryRun, classifiedEmails }) {
  if (!preview && !report && !classifiedEmails?.length) return null;

  const counts =
    preview?.category_counts || report?.top_categories || {};
  const emails =
    classifiedEmails ||
    preview?.classified_emails ||
    preview?.samples ||
    [];
  const estimated =
    preview?.estimated_actions ?? report?.actions_applied ?? 0;
  const wouldLabel =
    emails.filter((e) => e.would_apply_label).length ||
    preview?.would_apply_labels?.length ||
    estimated;

  const sortedCats = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const [filter, setFilter] = useState("all");

  const filtered = useMemo(() => {
    if (filter === "label") {
      return emails.filter((e) => e.would_apply_label);
    }
    if (filter === "skip") {
      return emails.filter((e) => !e.would_apply_label);
    }
    return emails;
  }, [emails, filter]);

  return (
    <div className="preview-panel">
      <h3>{dryRun ? "Draft organization — nothing changed in Gmail yet" : "Run summary"}</h3>
      <p className="text-muted">
        Inbox stays intact — suggested labels only, nothing archived or deleted.
      </p>
      <div className="metrics-grid preview-stats">
        <div>
          <div className="stat-label">Suggested labels</div>
          <div className="stat-value">{wouldLabel}</div>
        </div>
        <div>
          <div className="stat-label">New emails organized</div>
          <div className="stat-value">
            {report?.classified ?? emails.length ?? "—"}
          </div>
        </div>
        <div>
          <div className="stat-label">Already organized</div>
          <div className="stat-value">{report?.label_skipped ?? 0}</div>
        </div>
      </div>
      {sortedCats.length ? (
        <div style={{ marginTop: 12 }}>
          <div className="stat-label">Categories</div>
          <ul className="top-categories compact">
            {sortedCats.map(([cat, count]) => (
              <li key={cat}>
                <CategoryBadge category={cat} />
                <span>{count}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {emails.length ? (
        <div style={{ marginTop: 16 }}>
          <div className="preview-table-header">
            <div className="stat-label">
              All emails in this draft ({filtered.length}
              {filter !== "all" ? ` of ${emails.length}` : ""})
            </div>
            <div className="preview-filters">
              <button
                type="button"
                className={`btn btn-preset btn-sm ${filter === "all" ? "active" : ""}`}
                onClick={() => setFilter("all")}
              >
                All
              </button>
              <button
                type="button"
                className={`btn btn-preset btn-sm ${filter === "label" ? "active" : ""}`}
                onClick={() => setFilter("label")}
              >
                Will label
              </button>
              <button
                type="button"
                className={`btn btn-preset btn-sm ${filter === "skip" ? "active" : ""}`}
                onClick={() => setFilter("skip")}
              >
                No label
              </button>
            </div>
          </div>
          <div className="preview-table-wrap">
            <table className="data-table preview-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Sender</th>
                  <th>Subject</th>
                  <th>Conf.</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <tr key={s.message_id}>
                    <td>
                      <CategoryBadge category={s.category} />
                    </td>
                    <td className="truncate" title={s.sender}>
                      {s.sender || "—"}
                    </td>
                    <td className="truncate" title={s.subject}>
                      {s.subject || "(no subject)"}
                    </td>
                    <td>{((s.confidence ?? 0) * 100).toFixed(0)}%</td>
                    <td>
                      {s.would_apply_label ? (
                        <span className="preview-action-yes">Suggest label</span>
                      ) : (
                        <span
                          className="preview-action-skip"
                          title={s.skipped_reason || ""}
                        >
                          No label
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
