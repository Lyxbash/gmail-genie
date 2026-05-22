import axios from "axios";



const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";



export const api = axios.create({

  baseURL: API_BASE,

  timeout: 60000,

  headers: { "Content-Type": "application/json" },

});



/** Long-running inbox cycle — paginated scan + semantic can exceed 3 minutes. */

export const cycleApi = axios.create({

  baseURL: API_BASE,

  timeout: 300000,

  headers: { "Content-Type": "application/json" },

});



let categoryMetaCache = null;



import { stageLabelUser } from "../utils/userLabels";

export function stageToLabel(stage) {
  return stageLabelUser(stage);
}



/** User-facing message for cycle request failures (timeout, network, lock). */

export function formatCycleError(err) {

  const status = err.response?.status;

  const data = err.response?.data;

  if (status === 409) {

    return (

      data?.error ||

      "Inbox processing is already running. Wait for the current cycle to finish."

    );

  }

  const isTimeout =

    err.code === "ECONNABORTED" || /timeout/i.test(err.message || "");

  const isNetwork =

    err.message === "Network Error" || err.code === "ERR_NETWORK";

  if (isTimeout || isNetwork) {

    return (

      "Cycle is taking longer than expected. " +

      "The server may still be processing — check Activity or Cycle Status."

    );

  }

  const raw =
    (typeof data?.error === "string" && data.error) ||
    (typeof data?.detail === "string" && data.detail) ||
    err.message ||
    "";

  if (/bad parameter|API misuse|sqlite/i.test(raw)) {
    return (
      "Classification hit a database concurrency error while processing multiple " +
      "emails (common with custom queries that find more new mail). " +
      "Restart the backend, then retry. If it persists, report the issue."
    );
  }

  if (raw) return raw;

  return "Failed to run inbox cycle";

}



export async function getDashboardOverview() {

  const { data } = await api.get("/dashboard/overview");

  return data;

}



export async function getRecentActivity(limit = 50) {

  const { data } = await api.get("/dashboard/recent-activity", {

    params: { limit },

  });

  return data;

}



export async function getRecentFailures(limit = 50) {

  const { data } = await api.get("/dashboard/recent-failures", {

    params: { limit },

  });

  return data;

}



export async function getReviewQueue(limit = 50) {

  const { data } = await api.get("/review-queue", { params: { limit } });

  return data;

}



export async function getDailyMetrics(limit = 30) {

  const { data } = await api.get("/dashboard/daily-metrics", {

    params: { limit },

  });

  return data;

}



export async function getCategoryMetadata() {

  if (categoryMetaCache) return categoryMetaCache;

  const { data } = await api.get("/dashboard/category-metadata");

  categoryMetaCache = data;

  return data;

}



export function clearCategoryMetadataCache() {

  categoryMetaCache = null;

}



export async function getMetricsSummary() {

  const { data } = await api.get("/metrics-summary");

  return data;

}



export async function getCycleStatus() {

  const { data } = await api.get("/cycle-status");

  return data;

}



export async function getHealth() {

  const { data } = await api.get("/health");

  return data;

}



export async function getConfigSummary() {

  const { data } = await api.get("/config-summary");

  return data;

}



/** Build Gmail query for date-range presets (backend uses same scan pipeline). */
export function buildOrganizeQuery(days) {
  const d = parseInt(days, 10);
  if (!d || d < 1) return "newer_than:7d -in:sent -in:chats";
  return `newer_than:${d}d -in:sent -in:chats`;
}

export async function getOnboardingStatus() {
  const { data } = await api.get("/onboarding-status");
  return data;
}

export async function getUndoInfo() {
  const { data } = await api.get("/undo-last-cycle");
  return data;
}

export async function getPendingPreview() {
  const { data } = await api.get("/pending-preview");
  return data;
}

export async function dismissPendingPreview() {
  const { data } = await api.post("/pending-preview/dismiss");
  return data;
}

export async function undoLastCycle() {
  const { data } = await cycleApi.post("/undo-last-cycle");
  return data;
}

export async function runDailyCycle({
  dryRun = true,
  maxResults = 25,
  gmailQuery = null,
  forceReprocess = false,
} = {}) {
  const body = {
    max_results: maxResults,
    dry_run: dryRun,
    verbose: false,
    force_reprocess: forceReprocess,
    compact_report: true,
  };
  if (gmailQuery) body.gmail_query = gmailQuery;
  const { data } = await cycleApi.post("/run-daily-cycle", body);
  return data;
}



export async function submitCorrection({

  messageId,

  sender,

  correctedCategory,

  previousCategory,

}) {

  const { data } = await api.post("/correct-classification", {

    message_id: messageId || null,

    sender,

    corrected_category: correctedCategory,

    previous_category: previousCategory || null,

  });

  return data;

}



export async function debugClassify({ sender, subject, snippet = "" }) {

  const { data } = await api.post("/debug-classify", {

    sender,

    subject,

    snippet,

    run_full_classifier: false,

    save_trace: false,

  });

  return data;

}


