import { describe, expect, it } from "vitest";

import { endedWithoutResults, phaseLabel, scanStateStyle } from "@/lib/scanState";

describe("scan state style", () => {
  it("treats only a completed run as successful", () => {
    expect(scanStateStyle("completed").successful).toBe(true);
    for (const state of ["cancelled", "timed_out", "failed", "queued", "running", "analysing"]) {
      expect(scanStateStyle(state).successful).toBe(false);
    }
  });

  it("does not present a cancelled or timed-out run as a failure", () => {
    expect(scanStateStyle("cancelled").label).toBe("Cancelled");
    expect(scanStateStyle("timed_out").label).toBe("Timed out");
    expect(scanStateStyle("failed").label).toBe("Failed");
  });

  it("marks the terminal states and only those", () => {
    expect(["completed", "cancelled", "timed_out", "failed"].every((s) => scanStateStyle(s).terminal)).toBe(true);
    expect(["queued", "running", "analysing"].some((s) => scanStateStyle(s).terminal)).toBe(false);
  });

  it("shows a run with no state as queued, and an unknown state as failed", () => {
    expect(scanStateStyle(undefined).label).toBe("Queued");
    expect(scanStateStyle("exploded").label).toBe("Failed");
  });

  it("knows which terminal states produced no results", () => {
    expect(endedWithoutResults("completed")).toBe(false);
    expect(endedWithoutResults("cancelled")).toBe(true);
    expect(endedWithoutResults("timed_out")).toBe(true);
    expect(endedWithoutResults("running")).toBe(false);
  });
});

describe("phase labels", () => {
  it("never shows the raw stream identifier to an operator", () => {
    expect(phaseLabel("phase_started")).toBe("Running checks");
    expect(phaseLabel("scan_queued")).toBe("Queued");
    expect(phaseLabel("evidence_saved")).toBe("Saving evidence");
    expect(phaseLabel("report_written")).toBe("Writing reports");
  });

  it("falls back rather than rendering an unmapped identifier", () => {
    expect(phaseLabel("some_new_backend_phase")).toBe("Running");
    expect(phaseLabel(null)).toBe("Running");
    expect(phaseLabel("", "Idle")).toBe("Idle");
  });
});
