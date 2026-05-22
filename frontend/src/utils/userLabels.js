/** User-facing labels — hide engineering terminology in default UI. */

export function confidenceBand(confidence) {
  const c = Number(confidence);
  if (Number.isNaN(c)) return { label: "Unknown", level: "low" };
  if (c >= 0.85) return { label: "High confidence", level: "high" };
  if (c >= 0.7) return { label: "Medium confidence", level: "medium" };
  return { label: "Needs review", level: "low" };
}

const REASON_LABELS = {
  low_confidence: "Needs review",
  low_score_margin: "Close call between categories",
  semantic_fallback: "AI reviewed",
  groq_escalation: "AI reviewed (escalated)",
  rules_verified: "AI verified",
  llm_path: "AI reviewed",
  ambiguous: "Uncertain classification",
};

export function reviewReasonLabel(reason) {
  if (!reason) return "Needs review";
  const key = String(reason).toLowerCase().replace(/\s+/g, "_");
  return REASON_LABELS[key] || REASON_LABELS[reason] || "Needs review";
}

export function stageLabelUser(stage) {
  const map = {
    scanning: "Scanning your inbox…",
    skipping_labelled: "Skipping already organized mail…",
    skipping: "Skipping already organized mail…",
    classifying: "Organizing emails…",
    applying_actions: "Applying suggested labels…",
    complete: "Done",
    failed: "Something went wrong",
    idle: "Ready",
  };
  return map[stage] || map.idle;
}
