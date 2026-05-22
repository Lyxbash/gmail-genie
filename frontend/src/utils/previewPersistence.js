const PREVIEW_KEY = "gmail-genie-pending-preview";
const DISMISS_KEY = "gmail-genie-dismissed-preview-id";

export function savePendingPreview(cycleResult, pendingParams) {
  try {
    const completedAt =
      cycleResult?.cycle_status?.last_successful_cycle?.completed_at ||
      cycleResult?.completed_at ||
      new Date().toISOString();
    sessionStorage.setItem(
      PREVIEW_KEY,
      JSON.stringify({
        result: cycleResult,
        params: pendingParams,
        savedAt: Date.now(),
        completedAt,
      })
    );
    sessionStorage.removeItem(DISMISS_KEY);
  } catch {
    /* quota / private mode */
  }
}

export function loadPendingPreview() {
  try {
    const raw = sessionStorage.getItem(PREVIEW_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearPendingPreview() {
  try {
    sessionStorage.removeItem(PREVIEW_KEY);
  } catch {
    /* ignore */
  }
}

export function dismissPreview(completedAt) {
  if (completedAt) {
    try {
      sessionStorage.setItem(DISMISS_KEY, completedAt);
    } catch {
      /* ignore */
    }
  }
  clearPendingPreview();
}

export function isPreviewDismissed(completedAt) {
  if (!completedAt) return false;
  try {
    return sessionStorage.getItem(DISMISS_KEY) === completedAt;
  } catch {
    return false;
  }
}

/** Rebuild API-shaped result from dashboard last_successful_cycle. */
export function cycleSnapshotToPreviewResult(snapshot) {
  if (!snapshot?.dry_run || snapshot?.awaiting_apply === false) return null;
  const emails =
    snapshot.classified_emails ||
    snapshot.preview?.classified_emails ||
    [];
  return {
    dry_run: true,
    success: true,
    awaiting_apply: true,
    completed_at: snapshot.completed_at,
    classified: snapshot.classified,
    classified_emails: emails,
    pending_apply: snapshot.pending_apply,
    report: {
      classified: snapshot.classified,
      label_skipped: snapshot.label_skipped,
      dedup_skipped: snapshot.dedup_skipped,
      actions_applied: snapshot.actions_applied,
      top_categories: snapshot.preview?.category_counts || {},
    },
    preview: {
      classified_emails: emails,
      would_apply_labels: snapshot.preview?.would_apply_labels || [],
      would_mark_read: snapshot.preview?.would_mark_read || [],
      estimated_actions: snapshot.actions_applied,
      category_counts: snapshot.preview?.category_counts,
    },
  };
}

export function applyPendingParamsToForm(snapshot, setters) {
  const pa = snapshot?.pending_apply;
  if (!pa) return;
  const q = pa.gmail_query || "";
  const dayMatch = q.match(/newer_than:(\d+)d/i);
  if (dayMatch) {
    setters.setSelectedDays(parseInt(dayMatch[1], 10));
    setters.setUseCustomQuery(false);
  } else if (q) {
    setters.setCustomQuery(q);
    setters.setUseCustomQuery(true);
  }
  if (pa.max_results) setters.setTargetInput(String(pa.max_results));
  if (pa.force_reprocess != null) setters.setForceReprocess(Boolean(pa.force_reprocess));
}
