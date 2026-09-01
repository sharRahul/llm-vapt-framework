import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AssetFindingCard } from "@/components/navigation/AssetFindingCard";
import type { Asset, Finding } from "@/types";

const finding = {
  id: "LLM01",
  assetId: "scan-1",
  title: "Prompt boundary",
  severity: "high",
  riskScore: 82,
  status: "open",
} as Finding;

function asset(overrides: Partial<Asset> = {}): Asset {
  return {
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
    ...overrides,
  } as Asset;
}

function renderCard(overrides: Partial<Asset> = {}, props: Partial<Parameters<typeof AssetFindingCard>[0]> = {}) {
  const onSelectFinding = vi.fn();
  render(
    <AssetFindingCard
      asset={asset(overrides)}
      findings={[finding]}
      expanded={false}
      selectedFindingId={null}
      onToggle={vi.fn()}
      onSelectFinding={onSelectFinding}
      {...props}
    />,
  );
  return { onSelectFinding };
}

describe("AssetFindingCard", () => {
  it("shows severity, risk and a finding count for a completed scan", () => {
    renderCard();
    expect(screen.getByText("1 vuln")).toBeInTheDocument();
    expect(screen.queryByText(/^Scan /)).not.toBeInTheDocument();
  });

  it("pluralises the finding count", () => {
    renderCard({ vulnerabilityCount: 3 });
    expect(screen.getByText("3 vulns")).toBeInTheDocument();
  });

  it.each([
    ["cancelled", "Scan cancelled"],
    ["timed_out", "Scan timed out"],
    ["failed", "Scan failed"],
  ])("names the actual outcome for a %s run instead of a clean result", (status, label) => {
    renderCard({ scanStatus: status as Asset["scanStatus"], vulnerabilityCount: 0, highestSeverity: "info" });
    expect(screen.getByText(label)).toBeInTheDocument();
    // "info / 0 vulns" on an unfinished run would read as an all-clear.
    expect(screen.queryByText("0 vulns")).not.toBeInTheDocument();
  });

  it("shows the backend's reason when a run did not finish", () => {
    renderCard({ scanStatus: "timed_out", scanError: "exceeded the configured budget" });
    expect(screen.getByText("exceeded the configured budget")).toBeInTheDocument();
  });

  it("selects a finding when its row is activated", async () => {
    const { onSelectFinding } = renderCard({}, { expanded: true });
    await userEvent.click(screen.getByText("Prompt boundary"));
    expect(onSelectFinding).toHaveBeenCalledWith("LLM01");
  });
});
