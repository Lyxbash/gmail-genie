import { useCallback, useEffect, useRef, useState } from "react";
import {
  buildOrganizeQuery,
  dismissPendingPreview,
  formatCycleError,
  getCycleStatus,
  getPendingPreview,
  getUndoInfo,
  runDailyCycle,
  stageToLabel,
  undoLastCycle,
} from "../api/client";
import {
  hasCompletedFirstApply,
  markFirstApplyComplete,
} from "../hooks/useDeveloperMode";
import CyclePreview from "./CyclePreview";
import LabelSetupNotice from "./LabelSetupNotice";
import Spinner from "./Spinner";
import {
  applyPendingParamsToForm,
  clearPendingPreview,
  cycleSnapshotToPreviewResult,
  dismissPreview,
  isPreviewDismissed,
  loadPendingPreview,
  savePendingPreview,
} from "../utils/previewPersistence";

const DATE_PRESETS = [
  { days: 1, label: "Last 1 day" },
  { days: 3, label: "Last 3 days" },
  { days: 7, label: "Last 7 days" },
  { days: 14, label: "Last 14 days" },
];

const TARGET_PRESETS = [10, 25, 50];

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function elapsedFromStartedAt(startedAt) {
  if (!startedAt) return 0;
  const start = new Date(startedAt).getTime();
  if (Number.isNaN(start)) return 0;
  return Math.max(0, Math.floor((Date.now() - start) / 1000));
}

function parseTargetInput(raw) {
  const n = parseInt(String(raw).replace(/^0+/, "") || "25", 10);
  return Math.min(100, Math.max(1, Number.isNaN(n) ? 25 : n));
}

function restoreFormFromPending(pendingApply, setters) {
  applyPendingParamsToForm({ pending_apply: pendingApply }, setters);
}

export default function OrganizeInbox({
  onComplete,
  onCycleRunningChange,
  onLiveProgress,
  serverPendingSnapshot = null,
}) {
  const [selectedDays, setSelectedDays] = useState(7);
  const [customQuery, setCustomQuery] = useState("");
  const [useCustomQuery, setUseCustomQuery] = useState(false);
  const [targetInput, setTargetInput] = useState("25");
  const [dryRun, setDryRun] = useState(true);
  const [forceReprocess, setForceReprocess] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [loading, setLoading] = useState(false);
  const [awaitingApply, setAwaitingApply] = useState(false);
  const [previewResult, setPreviewResult] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [statusText, setStatusText] = useState("");
  const [heartbeatStale, setHeartbeatStale] = useState(false);
  const [undoAvailable, setUndoAvailable] = useState(false);
  const [undoLoading, setUndoLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const startedAtRef = useRef(null);
  const timerRef = useRef(null);
  const pollRef = useRef(null);
  const pendingParamsRef = useRef(null);

  const [hasApplied, setHasApplied] = useState(hasCompletedFirstApply);
  const firstRun = !hasApplied;

  const setRunning = useCallback(
    (running) => onCycleRunningChange?.(running),
    [onCycleRunningChange]
  );

  const refreshUndo = useCallback(async () => {
    try {
      const info = await getUndoInfo();
      setUndoAvailable(Boolean(info?.undo?.can_undo));
    } catch {
      setUndoAvailable(false);
    }
  }, []);

  const applyStatus = useCallback(
    (st) => {
      if (!st?.running) return;
      if (st.current_stage) setStatusText(stageToLabel(st.current_stage));
      setHeartbeatStale(Boolean(st.heartbeat_stale));
      if (st.started_at) startedAtRef.current = st.started_at;
      const sec =
        st.elapsed_seconds != null
          ? Math.floor(st.elapsed_seconds)
          : elapsedFromStartedAt(st.started_at);
      setElapsed(sec);
      onLiveProgress?.({
        active: true,
        pages_scanned: 0,
        fetched_total: st.fetched_total ?? 0,
        classified: st.classified ?? 0,
        partial_fetch_failures: 0,
        current_stage: st.current_stage,
        started_at: st.started_at,
        elapsed_seconds: sec,
        heartbeat_stale: Boolean(st.heartbeat_stale),
      });
    },
    [onLiveProgress]
  );

  const pollStatus = useCallback(async () => {
    try {
      const st = await getCycleStatus();
      if (st.running) applyStatus(st);
    } catch {
      /* ignore */
    }
  }, [applyStatus]);

  const restorePreviewState = useCallback(
    (result, params) => {
      if (!result?.dry_run || result?.awaiting_apply === false) return;
      const completedAt = result.completed_at || serverPendingSnapshot?.completed_at;
      if (isPreviewDismissed(completedAt)) return;
      setPreviewResult(result);
      setAwaitingApply(true);
      pendingParamsRef.current = params || result.pending_apply;
      if (params || result.pending_apply) {
        restoreFormFromPending(params || result.pending_apply, {
          setSelectedDays,
          setUseCustomQuery,
          setCustomQuery,
          setTargetInput,
          setForceReprocess,
        });
      }
      setStatusText("Preview ready — review labels before applying");
    },
    [serverPendingSnapshot]
  );

  useEffect(() => {
    refreshUndo();
    let mounted = true;

    const stored = loadPendingPreview();
    if (stored?.result) {
      restorePreviewState(stored.result, stored.params);
    } else if (serverPendingSnapshot) {
      const rebuilt = cycleSnapshotToPreviewResult(serverPendingSnapshot);
      if (rebuilt) {
        restorePreviewState(rebuilt, serverPendingSnapshot.pending_apply);
      }
    }

    (async () => {
      try {
        const [st, pendingRes] = await Promise.all([
          getCycleStatus(),
          getPendingPreview(),
        ]);
        if (!mounted) return;
        if (st.running) {
          setLoading(true);
          setRunning(true);
          applyStatus(st);
          return;
        }
        const pending = pendingRes?.pending;
        if (pending?.awaiting_apply && !loadPendingPreview()) {
          const rebuilt = cycleSnapshotToPreviewResult(pending);
          if (rebuilt) restorePreviewState(rebuilt, pending.pending_apply);
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      mounted = false;
    };
  }, [setRunning, applyStatus, refreshUndo, restorePreviewState, serverPendingSnapshot]);

  useEffect(() => {
    if (loading) {
      if (!startedAtRef.current) {
        startedAtRef.current = new Date().toISOString();
      }
      timerRef.current = setInterval(() => {
        setElapsed(elapsedFromStartedAt(startedAtRef.current));
      }, 1000);
      pollStatus();
      pollRef.current = setInterval(pollStatus, 2000);
    } else {
      clearInterval(timerRef.current);
      clearInterval(pollRef.current);
      if (!awaitingApply) {
        startedAtRef.current = null;
      }
      if (!loading && !awaitingApply) {
        onLiveProgress?.({ active: false });
      }
    }
    return () => {
      clearInterval(timerRef.current);
      clearInterval(pollRef.current);
    };
  }, [loading, pollStatus, onLiveProgress, awaitingApply]);

  function buildParams(overrides = {}) {
    const maxResults = parseTargetInput(targetInput);
    const gmailQuery = useCustomQuery
      ? customQuery.trim()
      : buildOrganizeQuery(selectedDays);
    return {
      maxResults,
      dryRun: overrides.dryRun ?? dryRun,
      gmailQuery,
      forceReprocess,
      ...overrides,
    };
  }

  async function runCycle(overrides = {}) {
    const params = buildParams(overrides);
    pendingParamsRef.current = params;
    const isApply = params.dryRun === false;
    if (isApply) setApplying(true);
    setLoading(true);
    setRunning(true);
    setError(null);
    setResult(null);
    setPreviewResult(null);
    setAwaitingApply(false);
    startedAtRef.current = null;
    onLiveProgress?.({
      active: true,
      pages_scanned: 0,
      fetched_total: 0,
      classified: 0,
      current_stage: "scanning",
    });

    try {
      const data = await runDailyCycle(params);
      if (params.dryRun) {
        setPreviewResult(data);
        setAwaitingApply(true);
        savePendingPreview(data, params);
        setStatusText("Preview ready — review labels before applying");
      } else {
        clearPendingPreview();
        dismissPreview(data.completed_at);
        setResult(data);
        if (!params.dryRun) {
          markFirstApplyComplete();
          setHasApplied(true);
          refreshUndo();
        }
        onComplete?.(data);
      }
    } catch (err) {
      setError(formatCycleError(err));
      onComplete?.();
    } finally {
      setLoading(false);
      setRunning(false);
      setApplying(false);
    }
  }

  async function handleOrganize() {
    const forcePreview = firstRun || !hasCompletedFirstApply();
    if (forcePreview) {
      await runCycle({ dryRun: true });
      return;
    }
    await runCycle({ dryRun });
  }

  async function handleApplyLabels() {
    const params = pendingParamsRef.current || buildParams();
    await runCycle({ ...params, dryRun: false });
    setAwaitingApply(false);
    setPreviewResult(null);
    clearPendingPreview();
    try {
      await dismissPendingPreview();
    } catch {
      /* ignore */
    }
  }

  async function handleDismissPreview() {
    const completedAt =
      previewResult?.completed_at || serverPendingSnapshot?.completed_at;
    dismissPreview(completedAt);
    clearPendingPreview();
    setAwaitingApply(false);
    setPreviewResult(null);
    try {
      await dismissPendingPreview();
    } catch {
      /* ignore */
    }
  }

  async function handleUndo() {
    setUndoLoading(true);
    setError(null);
    try {
      await undoLastCycle();
      setUndoAvailable(false);
      setResult(null);
      onComplete?.();
    } catch (err) {
      setError(err.response?.data?.error || err.message || "Undo failed");
    } finally {
      setUndoLoading(false);
    }
  }

  const displayResult = result || previewResult;
  const isPartial =
    displayResult?.status === "partial_success" ||
    (displayResult?.partial_fetch_failures ?? 0) > 0;
  const runLimit =
    displayResult?.pending_apply?.max_results ??
    pendingParamsRef.current?.maxResults ??
    parseTargetInput(targetInput);

  return (
    <div className="card organize-card">
      <h2>Organize my inbox</h2>
      <p className="text-muted" style={{ marginTop: 0 }}>
        Local AI organizer — labels only. Your inbox stays visible; nothing is
        archived or deleted. You can undo the last apply run.
      </p>
      {firstRun ? (
        <div className="alert alert-info first-run-banner">
          <strong>First run:</strong> Preview only — review suggested labels, then
          apply when ready. Gmail is not changed until you confirm.
        </div>
      ) : null}
      <LabelSetupNotice compact />

      <div className="organize-presets">
        <span className="preset-label">Recent mail</span>
        <div className="preset-buttons">
          {DATE_PRESETS.map((p) => (
            <button
              key={p.days}
              type="button"
              className={`btn btn-preset ${!useCustomQuery && selectedDays === p.days ? "active" : ""}`}
              disabled={loading || applying}
              onClick={() => {
                setUseCustomQuery(false);
                setSelectedDays(p.days);
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
        <p className="scan-limit-hint text-muted">
          Scans this date range newest-first until up to{" "}
          <strong>{parseTargetInput(targetInput)}</strong> new emails need labels.
          Mail Genie already labelled is skipped.{" "}
          <button
            type="button"
            className="btn btn-link inline-link"
            onClick={() => setShowAdvanced(true)}
          >
            Change limit in Advanced
          </button>
        </p>
      </div>

      <button
        type="button"
        className="btn btn-link advanced-toggle"
        onClick={() => setShowAdvanced((v) => !v)}
      >
        {showAdvanced ? "Hide" : "Show"} advanced options
      </button>

      {showAdvanced ? (
        <div className="advanced-panel">
          <label className="advanced-row">
            <span>Custom Gmail query</span>
            <input
              type="text"
              placeholder="newer_than:30d -in:sent -in:chats"
              value={customQuery}
              onChange={(e) => {
                setCustomQuery(e.target.value);
                setUseCustomQuery(true);
              }}
            />
            {useCustomQuery && customQuery.trim() ? (
              <span className="advanced-hint">
                Active query (date presets ignored):{" "}
                <code>{customQuery.trim()}</code>
              </span>
            ) : (
              <span className="advanced-hint">
                Typing here overrides the date buttons. Include{" "}
                <code>-in:sent -in:chats</code> like the presets.
              </span>
            )}
          </label>
          <label className="advanced-row">
            <span>Max new emails per run</span>
            <span className="advanced-hint">
              Higher = longer run (up to 100). Does not re-label mail Genie already
              organised.
            </span>
            <div className="target-input-row">
              {TARGET_PRESETS.map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`btn btn-preset btn-sm ${targetInput === String(n) ? "active" : ""}`}
                  onClick={() => setTargetInput(String(n))}
                  disabled={loading}
                >
                  {n}
                </button>
              ))}
              <input
                type="number"
                min={1}
                max={100}
                value={targetInput}
                onChange={(e) => {
                  const v = e.target.value.replace(/\D/g, "");
                  setTargetInput(v === "" ? "" : String(parseTargetInput(v)));
                }}
                onBlur={() => setTargetInput(String(parseTargetInput(targetInput)))}
                style={{ width: 72 }}
                disabled={loading}
              />
            </div>
          </label>
          <label>
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              disabled={loading || firstRun}
            />
            Dry run (preview only)
            {firstRun ? " — required for first run" : ""}
          </label>
          <label>
            <input
              type="checkbox"
              checked={forceReprocess}
              onChange={(e) => setForceReprocess(e.target.checked)}
              disabled={loading}
            />
            Force reprocess (ignore dedup memory)
          </label>
        </div>
      ) : null}

      <div className="organize-actions">
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleOrganize}
          disabled={loading || undoLoading || applying}
        >
          {loading
            ? applying
              ? "Applying labels…"
              : `Organizing… (${formatElapsed(elapsed)})`
            : firstRun
              ? "Preview organization"
              : dryRun
                ? "Preview organization"
                : "Organize inbox"}
        </button>
        {undoAvailable ? (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleUndo}
            disabled={loading || undoLoading || applying}
            title="Removes only Genie labels from the last apply — mail stays in inbox"
          >
            {undoLoading ? (
              <>
                <Spinner size={12} /> Undoing…
              </>
            ) : (
              "Undo last apply"
            )}
          </button>
        ) : null}
      </div>

      {loading ? (
        <div className="alert alert-info" style={{ marginTop: 12 }}>
          <strong>Active:</strong> {statusText || "Processing on your machine…"}
          <div className="text-muted" style={{ marginTop: 6, fontSize: 12 }}>
            Still processing on server — safe to refresh; timer follows backend.
          </div>
          {heartbeatStale ? (
            <div className="alert alert-warning" style={{ marginTop: 8 }}>
              Cycle appears stalled — backend may be retrying Gmail requests.
            </div>
          ) : null}
        </div>
      ) : null}

      {error ? <div className="alert alert-error">{error}</div> : null}

      {awaitingApply && previewResult ? (
        <>
          <p className="run-scan-summary text-muted">
            Draft session: <strong>{previewResult.classified ?? 0}</strong> new organized
            · <strong>{previewResult.label_skipped ?? 0}</strong> already organized
            · limit <strong>{runLimit}</strong> per run
          </p>
          <CyclePreview
            preview={previewResult.preview}
            report={previewResult.report}
            classifiedEmails={
              previewResult.classified_emails ||
              previewResult.preview?.classified_emails
            }
            dryRun
          />
          <div className="apply-bar">
            <p>
              <strong>Draft organization session</strong> — saved until you apply or
              dismiss (survives page navigation). Applying adds Gmail labels only;
              inbox preserved.
            </p>
            <LabelSetupNotice />
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleApplyLabels}
              disabled={loading || applying}
            >
              {applying ? (
                <>
                  <Spinner size={12} /> Applying labels…
                </>
              ) : (
                "Apply labels to Gmail"
              )}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleDismissPreview}
            >
              Dismiss preview
            </button>
          </div>
        </>
      ) : null}

      {result && !awaitingApply ? (
        <div className={isPartial ? "alert alert-warning" : "alert alert-success"}>
          <strong>
            {isPartial
              ? "Organized with warnings"
              : result.dry_run
                ? "Preview complete"
                : "Labels applied — inbox preserved"}
          </strong>
          <p className="run-scan-summary text-muted" style={{ marginTop: 8 }}>
            <strong>{result.classified ?? 0}</strong> new organized ·{" "}
            <strong>{result.label_skipped ?? 0}</strong> already organized · limit{" "}
            <strong>{runLimit}</strong>
          </p>
          <CyclePreview
            preview={result.preview}
            report={result.report}
            classifiedEmails={
              result.classified_emails || result.preview?.classified_emails
            }
            dryRun={result.dry_run}
          />
        </div>
      ) : null}
    </div>
  );
}
