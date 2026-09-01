import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AssetNavigationPane } from "@/components/navigation/AssetNavigationPane";
import type { Asset, Finding } from "@/types";

const finding = {
  id: "LLM01",
  assetId: "scan-1",
  title: "Prompt boundary",
  severity: "high",
  riskScore: 82,
  status: "open",
  affectedPath: "Prompt and instruction layer",
} as Finding;

const asset = {
  id: "scan-1",
  name: "agent · baseline",
  type: "ai_agent",
  locator: "scan:1",
  vulnerabilityCount: 1,
  highestSeverity: "high",
  riskScore: 82,
  lastScanned: new Date().toISOString(),
  findingIds: ["LLM01"],
  scanStatus: "completed",
  scanError: null,
} as Asset;

function renderPane(assets: Asset[]) {
  render(
    <AssetNavigationPane
      assets={assets}
      findingsById={{ LLM01: finding }}
      selectedFindingId={null}
      onSelectFinding={vi.fn()}
    />,
  );
}

describe("AssetNavigationPane", () => {
  it("does not tell the operator to adjust a filter they never set", () => {
    renderPane([]);
    expect(screen.getByText("No scans yet")).toBeInTheDocument();
    expect(screen.queryByText("No assets match")).not.toBeInTheDocument();
  });

  it("blames the filter only once a filter is actually hiding something", async () => {
    renderPane([asset]);
    await userEvent.type(screen.getByPlaceholderText(/Filter assets/i), "nothing-matches-this");
    expect(screen.getByText("No assets match")).toBeInTheDocument();
    expect(screen.queryByText("No scans yet")).not.toBeInTheDocument();
  });

  it("lists a scanned asset", () => {
    renderPane([asset]);
    expect(screen.getByText("agent · baseline")).toBeInTheDocument();
  });
});
