import { useCallback, useEffect, useState } from "react";
import { getRecentActivity } from "../api/client";
import ActivityTable from "../components/ActivityTable";
import EmptyState from "../components/EmptyState";
import { useDeveloperMode } from "../hooks/useDeveloperMode";
import Spinner from "../components/Spinner";

const REFRESH_MS = 60000;

export default function Activity() {
  const { developerMode } = useDeveloperMode();
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await getRecentActivity(50);
      setItems(data.items || []);
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load activity");
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
        <h1>Recent activity</h1>
        <p className="text-muted">
          Emails organized on this machine · inbox preserved in Gmail
        </p>
      </header>
      {error ? <div className="alert alert-error">{error}</div> : null}
      <div className="card">
        {loading ? (
          <div className="loading-row">
            <Spinner /> Loading activity…
          </div>
        ) : (
          <ActivityTable items={items} developerMode={developerMode} />
        )}
      </div>
    </div>
  );
}
