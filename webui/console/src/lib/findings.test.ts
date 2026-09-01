import { describe, expect, it } from "vitest";

import {
  distributionFor,
  latestScan,
  metricsFor,
  normaliseSeverity,
  normaliseStatus,
  riskScore,
  scanAsset,
  toFinding,
  trendLabel,
} from "@/lib/findings";
import type { BackendFinding, Finding, ScanJob } from "@/types";

const scan: ScanJob = {
  id: "scan-1",
  target: "agent",
  profile: "baseline",
  status: "completed",
  created_at: "2026-09-01T09:00:00Z",
  started_at: "2026-09-01T09:00:05Z",
  completed_at: "2026-09-01T09:01:00Z",
} as ScanJob;

function backendFinding(overrides: Partial<BackendFinding> = {}): BackendFinding {
  return {
    id: "LLM01",
    title: "Prompt boundary",
    severity: "high",
    owasp_id: "LLM01:2025",
    ...overrides,
  } as BackendFinding;
}

describe("severity and status normalisation", () => {
  it("keeps known severities and falls back to info", () => {
    expect(normaliseSeverity("CRITICAL")).toBe("critical");
    expect(normaliseSeverity("catastrophic")).toBe("info");
    expect(normaliseSeverity(undefined)).toBe("info");
  });

  it("keeps every persisted triage status and falls back to open", () => {
    for (const status of [
      "open",
      "pending_review",
      "auto_fix_available",
      "triaged",
      "in_progress",
      "accepted_risk",
      "false_positive",
      "fixed",
      "wont_fix",
    ]) {
      expect(normaliseStatus(status)).toBe(status);
    }
    expect(normaliseStatus("resolved-ish")).toBe("open");
  });
});

describe("risk scoring", () => {
  it("scales a 0-1 backend score onto 0-100", () => {
    expect(riskScore("high", { score: 0.42 })).toBe(42);
  });

  it("passes a 0-100 score through and clamps out-of-range values", () => {
    expect(riskScore("high", { score: 73 })).toBe(73);
    expect(riskScore("high", { score: 999 })).toBe(100);
    expect(riskScore("high", { score: -5 })).toBe(0);
  });

  it("falls back to severity when the backend sent no score", () => {
    expect(riskScore("critical", {})).toBe(95);
    expect(riskScore("info", {})).toBe(10);
  });
});

describe("toFinding", () => {
  it("prefers the persisted remediation state over the raw status", () => {
    const finding = toFinding(
      backendFinding({ status: "open", remediation_state: { status: "fixed" } as never }),
      "scan-1",
      0,
    );
    expect(finding.status).toBe("fixed");
    expect(finding.intelligence.policyStatus).toBe("pass");
  });

  it("says so plainly when a finding carried no structured evidence", () => {
    const finding = toFinding(backendFinding({ evidence: {} }), "scan-1", 0);
    expect(finding.vulnerableCode.code).toContain("No structured evidence");
  });

  it("carries provenance through instead of inventing it", () => {
    const finding = toFinding(
      backendFinding({ source: "inferred", confidence: "low", tool: "starter", observed_at: "2026-09-01T09:00:00Z" }),
      "scan-1",
      0,
    );
    expect(finding.source).toBe("inferred");
    expect(finding.confidence).toBe("low");
    expect(finding.tool).toBe("starter");
    expect(finding.observedAt).toBe("2026-09-01T09:00:00Z");
  });

  it("falls back to a stable id when the backend omitted one", () => {
    expect(toFinding(backendFinding({ id: undefined, owasp_id: undefined }), "scan-1", 4).id).toBe("finding-5");
  });
});

describe("dashboard aggregation", () => {
  const findings = [
    { severity: "critical", status: "open", riskScore: 95 },
    { severity: "high", status: "fixed", riskScore: 82 },
    { severity: "high", status: "triaged", riskScore: 80 },
    { severity: "low", status: "in_progress", riskScore: 32 },
  ] as Finding[];

  it("counts severities and pending reviews", () => {
    const metrics = metricsFor(findings, scan);
    expect(metrics.critical).toBe(1);
    expect(metrics.high).toBe(2);
    expect(metrics.low).toBe(1);
    expect(metrics.pendingReviews).toBe(2);
    expect(metrics.totalScanned).toBe(1);
  });

  it("reports a remediation rate of zero rather than NaN with no findings", () => {
    expect(metricsFor([], null).autoRemediationRate).toBe(0);
    expect(metricsFor([], null).totalScanned).toBe(0);
  });

  it("leaves severities with no findings out of the distribution", () => {
    expect(distributionFor(findings)).toEqual([
      { severity: "critical", count: 1 },
      { severity: "high", count: 2 },
      { severity: "low", count: 1 },
    ]);
  });
});

describe("scan asset", () => {
  it("takes the highest severity and the highest risk score present", () => {
    const asset = scanAsset(scan, [
      { id: "a", severity: "low", riskScore: 32 },
      { id: "b", severity: "critical", riskScore: 95 },
    ] as Finding[]);
    expect(asset.highestSeverity).toBe("critical");
    expect(asset.riskScore).toBe(95);
    expect(asset.vulnerabilityCount).toBe(2);
  });

  it("carries a failed run's status and reason onto the asset", () => {
    const asset = scanAsset({ ...scan, status: "timed_out", error: "budget exceeded" }, []);
    expect(asset.scanStatus).toBe("timed_out");
    expect(asset.scanError).toBe("budget exceeded");
  });
});

describe("latestScan", () => {
  it("picks the most recent run regardless of list order", () => {
    const older = { ...scan, id: "old", completed_at: "2026-08-01T00:00:00Z" };
    const newer = { ...scan, id: "new", completed_at: "2026-09-01T00:00:00Z" };
    expect(latestScan([older, newer])?.id).toBe("new");
    expect(latestScan([newer, older])?.id).toBe("new");
  });

  it("falls back to the start time for a run that has not finished", () => {
    const running = { ...scan, id: "running", status: "running", completed_at: undefined } as ScanJob;
    const old = { ...scan, id: "old", completed_at: "2026-01-01T00:00:00Z" };
    expect(latestScan([old, running])?.id).toBe("running");
  });

  it("returns null with no scans", () => {
    expect(latestScan([])).toBeNull();
  });
});

describe("trendLabel", () => {
  it("renders an ISO day as a short axis label", () => {
    expect(trendLabel("2026-09-01")).toMatch(/Sep/);
  });

  it("passes an unparseable value through rather than showing Invalid Date", () => {
    expect(trendLabel("not-a-date")).toBe("not-a-date");
  });
});
