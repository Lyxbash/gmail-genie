import { useEffect, useState } from "react";
import {
  getCategoryMetadata,
  submitCorrection,
  clearCategoryMetadataCache,
} from "../api/client";
import CategoryBadge from "./CategoryBadge";
import EmptyState from "./EmptyState";
import Spinner from "./Spinner";
import { confidenceBand, reviewReasonLabel } from "../utils/userLabels";

export default function ReviewQueueTable({
  items = [],
  onCorrected,
  developerMode = false,
}) {
  const [categories, setCategories] = useState([]);
  const [selections, setSelections] = useState({});
  const [submitting, setSubmitting] = useState({});
  const [messages, setMessages] = useState({});

  useEffect(() => {
    getCategoryMetadata().then((meta) => {
      setCategories(Object.keys(meta).sort());
    });
  }, []);

  function setSelection(id, category) {
    setSelections((prev) => ({ ...prev, [id]: category }));
  }

  async function handleSubmit(row) {
    const key = row.message_id || `${row.sender}|${row.subject}`;
    const corrected = selections[key] || row.predicted_category;
    setSubmitting((prev) => ({ ...prev, [key]: true }));
    setMessages((prev) => ({ ...prev, [key]: null }));
    try {
      const res = await submitCorrection({
        messageId: row.message_id,
        sender: row.sender,
        correctedCategory: corrected,
        previousCategory: row.predicted_category,
      });
      if (!res.ok) {
        setMessages((prev) => ({
          ...prev,
          [key]: res.error || "Could not save correction",
        }));
        return;
      }
      clearCategoryMetadataCache();
      setMessages((prev) => ({ ...prev, [key]: "Saved — future mail from this sender may improve" }));
      onCorrected?.();
    } catch (err) {
      setMessages((prev) => ({
        ...prev,
        [key]: err.response?.data?.error || err.message,
      }));
    } finally {
      setSubmitting((prev) => ({ ...prev, [key]: false }));
    }
  }

  if (!items.length) {
    return (
      <EmptyState
        title="Nothing to review"
        message="When Genie is unsure about a category, those emails appear here so you can confirm or fix them."
        icon="✓"
      />
    );
  }

  return (
    <div className="table-scroll-wrap">
      <table className="data-table review-table">
        <thead>
          <tr>
            <th>Sender</th>
            <th>Subject</th>
            <th>Suggested</th>
            <th>Confidence</th>
            {developerMode ? <th>Detail</th> : null}
            <th>Fix category</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((row, i) => {
            const key = row.message_id || `${row.sender}|${row.subject}|${i}`;
            const band = confidenceBand(row.confidence);
            return (
              <tr key={key}>
                <td className="truncate" title={row.sender}>
                  {row.sender}
                </td>
                <td className="truncate" title={row.subject}>
                  {row.subject}
                </td>
                <td>
                  <CategoryBadge category={row.predicted_category} />
                </td>
                <td>
                  <span className={`confidence-pill ${band.level}`}>
                    {band.label}
                  </span>
                  {developerMode ? (
                    <span className="dev-inline">
                      {(Number(row.confidence) * 100).toFixed(0)}%
                    </span>
                  ) : null}
                </td>
                {developerMode ? (
                  <td className="dev-cell">
                    <code>{row.reason}</code>
                    {row.score_margin != null ? (
                      <span className="dev-inline">margin {row.score_margin}</span>
                    ) : null}
                  </td>
                ) : null}
                <td>
                  <select
                    value={selections[key] || row.predicted_category}
                    onChange={(e) => setSelection(key, e.target.value)}
                    disabled={submitting[key]}
                    aria-label="Correct category"
                  >
                    {categories.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <button
                    type="button"
                    className="btn btn-sm btn-primary"
                    disabled={submitting[key]}
                    onClick={() => handleSubmit(row)}
                  >
                    {submitting[key] ? (
                      <>
                        <Spinner size={12} /> Saving
                      </>
                    ) : (
                      "Save correction"
                    )}
                  </button>
                  {messages[key] ? (
                    <div className="correction-msg">{messages[key]}</div>
                  ) : null}
                  {!developerMode && row.reason ? (
                    <div className="correction-hint">
                      {reviewReasonLabel(row.reason)}
                    </div>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
