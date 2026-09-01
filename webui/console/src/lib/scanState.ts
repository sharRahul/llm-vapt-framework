import type { ScanJobStatus } from "@/types";

/**
 * How each scan run state is presented.
 *
 * A cancelled or timed-out run is not a failure and must not read as one: an
 * operator who stopped a scan, and a target that never answered, are different
 * outcomes with different next steps.
 */
export interface ScanStateStyle {
  label: string;
  /** Terminal states end the run; the console stops streaming on them. */
  terminal: boolean;
  /** True only for states that produced complete results. */
  successful: boolean;
  className: string;
}

export const scanStateStyles: Record<ScanJobStatus, ScanStateStyle> = {
  queued: {
    label: "Queued",
    terminal: false,
    successful: false,
    className: "border-border bg-muted text-muted-foreground",
  },
  running: {
    label: "Running",
    terminal: false,
    successful: false,
    className: "border-slate bg-[color-mix(in_srgb,var(--accent-slate)_16%,transparent)] text-slate",
  },
  analysing: {
    label: "Analysing",
    terminal: false,
    successful: false,
    className: "border-slate bg-[color-mix(in_srgb,var(--accent-slate)_16%,transparent)] text-slate",
  },
  completed: {
    label: "Completed",
    terminal: true,
    successful: true,
    className: "border-severity-low bg-[color-mix(in_srgb,var(--sev-low)_14%,transparent)] text-severity-low",
  },
  cancelled: {
    label: "Cancelled",
    terminal: true,
    successful: false,
    className: "border-border bg-muted text-muted-foreground",
  },
  timed_out: {
    label: "Timed out",
    terminal: true,
    successful: false,
    className:
      "border-severity-medium bg-[color-mix(in_srgb,var(--sev-medium)_14%,transparent)] text-severity-medium",
  },
  failed: {
    label: "Failed",
    terminal: true,
    successful: false,
    className: "border-severity-high bg-[color-mix(in_srgb,var(--sev-high)_10%,transparent)] text-severity-high",
  },
};

export function scanStateStyle(status: string | undefined): ScanStateStyle {
  return scanStateStyles[(status || "queued") as ScanJobStatus] ?? scanStateStyles.failed;
}

/** True when a run ended without producing complete results. */
export function endedWithoutResults(status: string | undefined): boolean {
  const style = scanStateStyle(status);
  return style.terminal && !style.successful;
}

/**
 * Human label for a scan stream phase.
 *
 * The header showed the raw stream identifier — an operator saw
 * "phase_started" as the current phase, which names the protocol, not the work.
 */
const PHASE_LABELS: Record<string, string> = {
  queued: "Queued",
  scan_queued: "Queued",
  scan_started: "Starting",
  initialising: "Starting",
  target_validation: "Validating target",
  target_validated: "Target validated",
  phase_started: "Running checks",
  check_started: "Running checks",
  check_completed: "Running checks",
  finding_created: "Recording findings",
  finding: "Recording findings",
  evidence_saved: "Saving evidence",
  evidence: "Saving evidence",
  report_written: "Writing reports",
  report: "Writing reports",
  analysing: "Analysing",
  completed: "Completed",
  scan_completed: "Completed",
  failed: "Failed",
  scan_failed: "Failed",
  heartbeat: "Running",
};

export function phaseLabel(phase: string | null | undefined, fallback = "Running"): string {
  if (!phase) return fallback;
  return PHASE_LABELS[phase] ?? fallback;
}
