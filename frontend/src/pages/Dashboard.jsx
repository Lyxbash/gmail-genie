import { useCallback, useEffect, useState } from "react";
import {
  getDashboardOverview,
  getHealth,
  getReviewQueue,
  stageToLabel,
} from "../api/client";
import MetricCard from "../components/MetricCard";
import HealthIndicator from "../components/HealthIndicator";
import OrganizeInbox from "../components/OrganizeInbox";
import OnboardingChecklist from "../components/OnboardingChecklist";
import CategoryBadge from "../components/CategoryBadge";
import ActivityTable from "../components/ActivityTable";
import EmptyState from "../components/EmptyState";
import { useDeveloperMode } from "../hooks/useDeveloperMode";
import { Link } from "react-router-dom";

const REFRESH_MS = 45000;

const USER_CATEGORIES = [
  "Work",
  "Finance",
  "Security",
  "Job Alerts",
  "Job Applications",
  "Newsletters",
  "Promotions",
  "Social",
  "Education",
  "General",
];

function formatRelativeTime(iso) {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  const diffSec = Math.floor((Date.now() - then) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} mins ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} hours ago`;
  return `${Math.floor(diffSec / 86400)} days ago`;
}

export default function Dashboard() {
  const { developerMode, toggleDeveloperMode } = useDeveloperMode();
  const [overview, setOverview] = useState(null);
  const [health, setHealth] = useState(null);
  const [reviewCount, setReviewCount] = useState(0);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cycleRunning, setCycleRunning] = useState(false);
  const [liveProgress, setLiveProgress] = useState(null);

  const load = useCallback(async () => {
    try {
      const [ov, h, rq] = await Promise.all([
        getDashboardOverview(),
        getHealth(),
        getReviewQueue(50),
      ]);
      setOverview(ov);
      setHealth(h);
      setReviewCount(Array.isArray(rq) ? rq.length : 0);
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(() => {
      if (!cycleRunning) load();
    }, REFRESH_MS);
    return () => clearInterval(id);
  }, [load, cycleRunning]);

  if (loading && !overview) {
    return (
      <div className="page-skeleton">
        <div className="skeleton-bar" />
        <div className="skeleton-card" />
        <div className="skeleton-card" />
      </div>
    );
  }

  const current = overview?.current_cycle || {};
  const lastSuccess = overview?.last_successful_cycle;
  const pendingPreviewSnapshot =
    lastSuccess?.dry_run && lastSuccess?.awaiting_apply ? lastSuccess : null;
  const session = overview?.session_metrics || {};
  const lastRun = current;
  const activeRun =
    cycleRunning && liveProgress?.active ? liveProgress : null;
  const lastPartialFailures =
    lastRun.partial_fetch_failures ??
    lastSuccess?.partial_fetch_failures ??
    0;
  const activeElapsed =
    activeRun?.elapsed_seconds != null
      ? Math.floor(activeRun.elapsed_seconds)
      : activeRun?.started_at
        ? Math.max(
            0,
            Math.floor(
              (Date.now() - new Date(activeRun.started_at).getTime()) / 1000
            )
          )
        : null;
  const topCats = overview?.top_categories || {};
  const sortedCats = Object.entries(topCats)
    .filter(([cat]) => USER_CATEGORIES.includes(cat) || developerMode)
    .sort((a, b) => b[1] - a[1]);
  const lastRunAgo = formatRelativeTime(
    lastSuccess?.completed_at || current.completed_at
  );
  const hasRuns =
    (lastRun.classified ?? 0) > 0 ||
    (lastSuccess?.classified ?? 0) > 0 ||
    (overview?.recent_activity?.length ?? 0) > 0;
  const gmailTransport = session.gmail_transport || {};
  const lastRunLatency = lastRun.latency || {};

  return (
    <div>
      <header className="page-header dashboard-hero">
        <div>
          <h1>Gmail Genie</h1>
          <p className="hero-tagline">
            Local AI inbox organizer — your email never leaves your machine.
          </p>
          <p className="text-muted refresh-note">
            Labels only · inbox preserved · nothing archived automatically
          </p>
        </div>
        <label className="dev-mode-toggle">
          <input
            type="checkbox"
            checked={developerMode}
            onChange={toggleDeveloperMode}
          />
          Developer mode
        </label>
      </header>

      {error ? <div className="alert alert-error">{error}</div> : null}

      {health && health.gmail_connected === false ? (
        <div className="alert alert-warning">
          Gmail API connectivity degraded — retries may be in progress.
        </div>
      ) : null}

      <OnboardingChecklist />

      <OrganizeInbox
        onComplete={load}
        onCycleRunningChange={setCycleRunning}
        onLiveProgress={setLiveProgress}
        serverPendingSnapshot={pendingPreviewSnapshot}
      />

      {activeRun ? (
        <div className="card card-active-run">
          <h2 className="active-title">● Active run</h2>
          <p className="text-muted" style={{ marginTop: 0 }}>
            {stageToLabel(activeRun.current_stage || "scanning")}
            {activeElapsed != null ? ` · ${activeElapsed}s` : ""}
          </p>
          {activeRun.heartbeat_stale ? (
            <div className="alert alert-warning">
              Still processing on server — Gmail retries may be in progress.
            </div>
          ) : null}
          <div className="metrics-grid">
            <MetricCard label="Fetched" value={activeRun.fetched_total ?? 0} />
            <MetricCard label="Organized" value={activeRun.classified ?? 0} />
            <MetricCard
              label="Elapsed"
              value={activeElapsed != null ? `${activeElapsed}s` : "…"}
            />
          </div>
        </div>
      ) : null}

      <div className={`card ${activeRun ? "card-muted" : ""}`}>
        <h2>Last run</h2>
        {!hasRuns ? (
          <EmptyState
            title="No runs yet"
            message="Run a preview to see how your recent mail would be organized — nothing changes until you apply labels."
            icon="✨"
          />
        ) : (
          <>
            {lastRunAgo ? (
              <p className="text-muted" style={{ marginTop: 0 }}>
                {lastRunAgo}
                {lastSuccess?.dry_run ? " · preview only" : " · labels applied"}
              </p>
            ) : null}
            {lastPartialFailures > 0 ? (
              <div className="alert alert-warning">
                Some messages could not be fetched ({lastPartialFailures}). Inbox
                preserved.
              </div>
            ) : null}
            <div className="metrics-grid">
              <MetricCard
                label="Organized"
                value={lastRun.classified ?? 0}
              />
              <MetricCard
                label="Labels applied"
                value={lastRun.actions_applied ?? 0}
              />
              <MetricCard
                label="Already organized"
                value={lastRun.label_skipped ?? 0}
              />
              <MetricCard
                label="Duration"
                value={
                  lastRun.cycle_duration_ms > 0
                    ? `${(lastRun.cycle_duration_ms / 1000).toFixed(1)}s`
                    : "—"
                }
              />
            </div>
          </>
        )}
      </div>

      <div className="two-col">
        <div className="card">
          <h2>Categories organized</h2>
          {sortedCats.length ? (
            <ul className="top-categories">
              {sortedCats.slice(0, 10).map(([cat, count]) => (
                <li key={cat}>
                  <CategoryBadge category={cat} />
                  <span>{count}</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No categories yet"
              message="Organize recent mail to see category breakdowns here."
              icon="🏷️"
            />
          )}
        </div>
        <div className="card">
          <div className="card-header-row">
            <h2>Review queue</h2>
            <Link to="/review" className="btn btn-sm btn-secondary">
              Open ({reviewCount})
            </Link>
          </div>
          {reviewCount === 0 ? (
            <EmptyState
              title="Queue is clear"
              message="Low-confidence emails will appear here for a quick check."
              icon="✓"
            />
          ) : (
            <p className="text-muted">
              {reviewCount} email{reviewCount === 1 ? "" : "s"} need a quick look.
            </p>
          )}
        </div>
      </div>

      <div className="card">
        <h2>Recent activity</h2>
        {(overview?.recent_activity?.length ?? 0) > 0 ? (
          <>
            <ActivityTable
              items={overview.recent_activity.slice(0, 8)}
              developerMode={developerMode}
            />
            <p style={{ marginTop: 12 }}>
              <Link to="/activity">View all activity →</Link>
            </p>
          </>
        ) : (
          <EmptyState
            title="No activity yet"
            message="Your organized emails will show up here after the first run."
          />
        )}
      </div>

      <div className="health-row" style={{ marginTop: "1rem" }}>
        <HealthIndicator label="Gmail" ok={health?.gmail_connected} />
        <HealthIndicator label="Ollama" ok={health?.ollama_available} warn />
        <HealthIndicator
          label="Groq"
          ok={health?.groq_enabled}
          warn={!health?.groq_enabled}
        />
        <HealthIndicator label="Database" ok={health?.database_ok} />
      </div>

      {developerMode ? (
        <>
          <div className="card" style={{ marginTop: "1rem" }}>
            <h2>Engineering diagnostics</h2>
            <p className="text-muted" style={{ marginTop: 0 }}>
              Session metrics — hidden in normal mode
            </p>
            <div className="metrics-grid">
              <MetricCard
                label="Semantic %"
                value={`${((session.semantic_rate ?? 0) * 100).toFixed(1)}%`}
              />
              <MetricCard
                label="Groq %"
                value={`${((session.groq_rate ?? 0) * 100).toFixed(1)}%`}
              />
              <MetricCard
                label="Gmail retries"
                value={gmailTransport.gmail_retry_count ?? 0}
              />
              <MetricCard
                label="SSL errors"
                value={gmailTransport.gmail_ssl_error_count ?? 0}
              />
            </div>
            {(lastRunLatency.total_cycle_ms || 0) > 0 ? (
              <div className="metrics-grid" style={{ marginTop: 12 }}>
                <MetricCard
                  label="Gmail fetch"
                  value={`${((lastRunLatency.gmail_fetch_messages_ms || 0) / 1000).toFixed(1)}s`}
                />
                <MetricCard
                  label="Classify"
                  value={`${((lastRunLatency.classify_ms || 0) / 1000).toFixed(1)}s`}
                />
                <MetricCard
                  label="Actions"
                  value={`${((lastRunLatency.actions_ms || 0) / 1000).toFixed(1)}s`}
                />
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
