import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
} from "recharts";
import { getDailyMetrics, getMetricsSummary } from "../api/client";
import MetricCard from "../components/MetricCard";
import { useDeveloperMode } from "../hooks/useDeveloperMode";
import EmptyState from "../components/EmptyState";
import Spinner from "../components/Spinner";

function pct(rate) {
  return `${((rate || 0) * 100).toFixed(1)}%`;
}

export default function Metrics() {
  const { developerMode } = useDeveloperMode();
  const [days, setDays] = useState([]);
  const [session, setSession] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [dm, ms] = await Promise.all([
        getDailyMetrics(30),
        getMetricsSummary(),
      ]);
      setDays((dm.days || []).slice().reverse());
      setSession(ms);
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  if (!developerMode) {
    return (
      <div>
        <header className="page-header">
          <h1>Insights</h1>
        </header>
        <div className="card">
          <EmptyState
            title="Developer mode required"
            message="Detailed session and inference metrics are available when Developer mode is enabled on the dashboard."
            icon="🔧"
          />
          <p style={{ marginTop: 16 }}>
            <Link to="/">← Back to dashboard</Link>
          </p>
        </div>
      </div>
    );
  }

  const processedData = days.map((d) => ({
    day: d.day?.slice(5) || d.day,
    processed: d.processed,
    semantic: d.semantic_used,
    groq: d.groq_used,
  }));

  const topCatMerged = {};
  days.forEach((d) => {
    Object.entries(d.top_categories || {}).forEach(([cat, n]) => {
      topCatMerged[cat] = (topCatMerged[cat] || 0) + n;
    });
  });
  const topCatData = Object.entries(topCatMerged)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, count]) => ({ name: name.slice(0, 18), count }));

  const lastRun = session?.last_cycle_run;
  const fromLastRun = Boolean(session?.from_last_cycle_run);
  const organized =
    session?.total_classified ?? lastRun?.classified ?? 0;

  if (loading) {
    return (
      <div className="loading-row">
        <Spinner /> Loading insights…
      </div>
    );
  }

  return (
    <div>
      <header className="page-header">
        <h1>Insights (developer)</h1>
        <p className="text-muted">
          Last completed run + daily snapshots. Counters reset when the API
          restarts; run organize again or refresh this page after a cycle.
        </p>
      </header>
      {error ? <div className="alert alert-error">{error}</div> : null}

      {session ? (
        <>
          {fromLastRun ? (
            <div className="alert alert-info" style={{ marginBottom: 12 }}>
              Showing metrics from your last completed run (API was restarted or
              session counters were empty).
            </div>
          ) : null}
          <div className="metrics-grid">
            <MetricCard label="Organized (last run)" value={organized} />
            <MetricCard
              label="Rules direct"
              value={pct(session.rules_direct_rate)}
            />
            <MetricCard
              label="AI verified"
              value={pct(session.rules_verified_rate)}
            />
            <MetricCard
              label="AI fallback"
              value={pct(
                session.semantic_fallback_rate ?? session.semantic_rate
              )}
            />
          </div>
          {lastRun ? (
            <p className="text-muted" style={{ marginTop: 8, fontSize: 13 }}>
              Last run: {lastRun.dry_run ? "preview" : "apply"} · classified{" "}
              {lastRun.classified ?? 0} · skipped labels{" "}
              {lastRun.label_skipped ?? 0}
              {lastRun.completed_at
                ? ` · ${new Date(lastRun.completed_at).toLocaleString()}`
                : ""}
            </p>
          ) : null}
        </>
      ) : null}

      {organized === 0 && !lastRun ? (
        <div className="card" style={{ marginTop: 16 }}>
          <EmptyState
            title="No runs recorded yet"
            message="Run Preview organization on the dashboard, then return here (or refresh)."
          />
        </div>
      ) : null}

      {days.length === 0 ? (
        <div className="card" style={{ marginTop: 16 }}>
          <EmptyState
            title="No daily history yet"
            message="Daily charts appear after you complete at least one organize run."
          />
        </div>
      ) : (
        <div className="two-col" style={{ marginTop: 16 }}>
          <div className="card">
            <h2>Emails organized per day</h2>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={processedData}>
                  <CartesianGrid stroke="#2d3a4f" />
                  <XAxis dataKey="day" stroke="#8b9cb3" fontSize={11} />
                  <YAxis stroke="#8b9cb3" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      background: "#1a2332",
                      border: "1px solid #2d3a4f",
                    }}
                  />
                  <Line type="monotone" dataKey="processed" stroke="#3b82f6" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="card">
            <h2>Top categories (30d)</h2>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topCatData}>
                  <CartesianGrid stroke="#2d3a4f" />
                  <XAxis dataKey="name" stroke="#8b9cb3" fontSize={10} />
                  <YAxis stroke="#8b9cb3" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      background: "#1a2332",
                      border: "1px solid #2d3a4f",
                    }}
                  />
                  <Bar dataKey="count" fill="#3b82f6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
