import { useCallback, useEffect, useState } from "react";
import { getReviewQueue } from "../api/client";
import ReviewQueueTable from "../components/ReviewQueueTable";
import { useDeveloperMode } from "../hooks/useDeveloperMode";
import Spinner from "../components/Spinner";

const REFRESH_MS = 45000;

export default function ReviewQueue() {
  const { developerMode } = useDeveloperMode();
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await getReviewQueue(50);
      setItems(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      setError(err.message || "Could not load review queue");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  return (
    <div>
      <header className="page-header">
        <h1>Review queue</h1>
        <p className="text-muted">
          Emails Genie was unsure about — pick the right category to improve future
          organization. Optional for most users.
        </p>
      </header>
      {error ? <div className="alert alert-error">{error}</div> : null}
      <div className="card">
        {loading ? (
          <div className="loading-row">
            <Spinner /> Loading review queue…
          </div>
        ) : (
          <ReviewQueueTable
            items={items}
            onCorrected={load}
            developerMode={developerMode}
          />
        )}
      </div>
    </div>
  );
}
