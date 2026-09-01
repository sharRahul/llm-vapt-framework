/**
 * The product rules that turn backend scan data into what the console shows.
 *
 * These lived inside `App.tsx`, which meant severity mapping, risk scoring, the
 * dashboard counters and the burn-down label could only be exercised by driving
 * a browser. They are pure functions over API shapes, so they belong here where
 * a test can state each rule directly.
 */

import { emptyDashboardMetrics } from "@/data/cleanState";
import type {
  Asset,
  BackendFinding,
  DashboardMetrics,
  Finding,
  FindingStatus,
  ScanJob,
  Severity,
  SeverityDistributionPoint,
} from "@/types";

export const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "info"];

/** Statuses that mean a reviewer still owes this finding attention. */
export const PENDING_REVIEW_STATUSES: FindingStatus[] = [
  "pending_review",
  "auto_fix_available",
  "triaged",
  "in_progress",
];

const FINDING_STATUSES: FindingStatus[] = [
  "open",
  "pending_review",
  "auto_fix_available",
  "triaged",
  "in_progress",
  "accepted_risk",
  "false_positive",
  "fixed",
  "wont_fix",
];

const SEVERITY_RANK: Record<Severity, number> = { critical: 4, high: 3, medium: 2, low: 1, info: 0 };

/** Anything the backend sends that is not a known severity is shown as info. */
export function normaliseSeverity(value: unknown): Severity {
  const severity = String(value || "info").toLowerCase();
  return SEVERITIES.includes(severity as Severity) ? (severity as Severity) : "info";
}

/** Anything the backend sends that is not a known status is shown as open. */
export function normaliseStatus(value: unknown): FindingStatus {
  const status = String(value || "open").toLowerCase();
  return FINDING_STATUSES.includes(status as FindingStatus) ? (status as FindingStatus) : "open";
}

export function formatEvidence(evidence: unknown): string {
  if (!evidence || (typeof evidence === "object" && Object.keys(evidence as Record<string, unknown>).length === 0)) {
    return "No structured evidence was returned for this finding. Review the generated report artifacts for additional context.";
  }
  return JSON.stringify(evidence, null, 2);
}

/**
 * The 0-100 risk score shown on a finding.
 *
 * The backend scores either 0-1 or 0-100 depending on the module, so both are
 * accepted and clamped. Without a score, severity decides.
 */
export function riskScore(severity: Severity, finding: Pick<BackendFinding, "score">): number {
  if (typeof finding.score === "number") {
    const score = finding.score <= 1 ? finding.score * 100 : finding.score;
    return Math.max(0, Math.min(100, Math.round(score)));
  }
  return { critical: 95, high: 82, medium: 58, low: 32, info: 10 }[severity];
}

export function toFinding(finding: BackendFinding, scanId: string, index: number): Finding {
  const id = String(finding.id || finding.owasp_id || `finding-${index + 1}`);
  const severity = normaliseSeverity(finding.severity);
  const recommendation =
    finding.recommendation || "Review the evidence, confirm applicability, and record the remediation decision.";
  const affectedComponent = finding.affected_component || "assessment target";
  const evidence = formatEvidence(finding.evidence);
  const state = finding.remediation_state;
  return {
    id,
    assetId: `scan-${scanId}`,
    title: finding.title || `${id} finding`,
    severity,
    riskScore: riskScore(severity, finding),
    status: normaliseStatus(state?.status || finding.status || "open"),
    affectedPath: affectedComponent,
    aiSummary: finding.description || recommendation,
    vulnerableCode: { language: "json", filename: `${id}-evidence.json`, code: evidence },
    remediation: {
      summary: recommendation,
      rationale: recommendation,
      confidence: state?.status === "fixed" ? 95 : 70,
      secureCode: { language: "text", filename: `${id}-remediation.txt`, code: recommendation },
    },
    cve: { id: null, description: "Framework finding generated from the active VulnoraIQ scan." },
    cwe: {
      id: "N/A",
      name: "AI security assessment finding",
      description: "Review the mapped OWASP/MITRE context and generated evidence before closure.",
    },
    intelligence: {
      owaspLlm: finding.owasp_id || "AITG",
      mitreAtlas: Array.isArray(finding.mitre_atlas) ? finding.mitre_atlas.join(", ") : "",
      exploitability: "theoretical",
      affectedComponent,
      recommendedPriority: severity,
      policyStatus: state?.status === "fixed" ? "pass" : "manual_review",
      complianceTags: [],
    },
    source: String(finding.source || "scanner_observed"),
    confidence: String(finding.confidence || "medium"),
    tool: String(finding.tool || "VulnoraIQ scanner"),
    observedAt: String(finding.observed_at || ""),
    limitations: String(finding.limitations || "Human review is required before acting on this finding."),
    report: [
      { title: "Evidence", body: evidence },
      { title: "Recommendation", body: recommendation },
      {
        title: "Review status",
        body: state
          ? `Status: ${state.status}. Updated by ${state.updated_by || "unknown"} at ${state.updated_at || "unknown"}.`
          : "No remediation state has been recorded yet.",
      },
    ],
  };
}

export function scanAsset(scan: ScanJob, findings: Finding[]): Asset {
  const highest = findings.reduce<Severity>(
    (current, finding) => (SEVERITY_RANK[finding.severity] > SEVERITY_RANK[current] ? finding.severity : current),
    "info",
  );
  return {
    id: `scan-${scan.id}`,
    name: `${scan.target} · ${scan.profile}`,
    type: "ai_agent",
    locator: `scan:${scan.id}`,
    vulnerabilityCount: findings.length,
    highestSeverity: highest,
    riskScore: findings.reduce((max, finding) => Math.max(max, finding.riskScore), 0),
    lastScanned: scan.completed_at || scan.started_at || scan.created_at || new Date().toISOString(),
    findingIds: findings.map((finding) => finding.id),
    scanStatus: scan.status,
    scanError: scan.error ?? null,
  };
}

/** The most recent run, by whichever timestamp the run has reached. */
export function latestScan(scans: ScanJob[]): ScanJob | null {
  return (
    [...scans].sort(
      (a, b) =>
        Date.parse(b.completed_at || b.started_at || b.created_at || "") -
        Date.parse(a.completed_at || a.started_at || a.created_at || ""),
    )[0] || null
  );
}

function severityCounts(findings: Finding[]): Record<Severity, number> {
  const counts = Object.fromEntries(SEVERITIES.map((severity) => [severity, 0])) as Record<Severity, number>;
  findings.forEach((finding) => {
    counts[finding.severity] += 1;
  });
  return counts;
}

export function metricsFor(findings: Finding[], activeScan: ScanJob | null): DashboardMetrics {
  const counts = severityCounts(findings);
  const fixed = findings.filter((finding) => finding.status === "fixed").length;
  const pendingReviews = findings.filter((finding) => PENDING_REVIEW_STATUSES.includes(finding.status)).length;
  return {
    ...emptyDashboardMetrics,
    totalScanned: activeScan ? 1 : 0,
    critical: counts.critical,
    high: counts.high,
    medium: counts.medium,
    low: counts.low,
    autoRemediationRate: findings.length ? Math.round((fixed / findings.length) * 100) : 0,
    pendingReviews,
  };
}

/** Only severities that actually occur reach the donut; zeroes are not slices. */
export function distributionFor(findings: Finding[]): SeverityDistributionPoint[] {
  const counts = severityCounts(findings);
  return SEVERITIES.map((severity) => ({ severity, count: counts[severity] })).filter((point) => point.count > 0);
}

/**
 * The burn-down axis label for one ISO day from `GET /api/trends`.
 *
 * An unparseable value is passed through rather than rendered as
 * "Invalid Date": the server's own string is at least true.
 */
export function trendLabel(isoDate: string): string {
  const parsed = new Date(`${isoDate}T00:00:00Z`);
  return Number.isNaN(parsed.getTime())
    ? isoDate
    : parsed.toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" });
}
