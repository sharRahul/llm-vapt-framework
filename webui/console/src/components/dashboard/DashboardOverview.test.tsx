import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardOverview } from "@/components/dashboard/DashboardOverview";
import { emptyDashboardMetrics } from "@/data/cleanState";

const trend = [
  { date: "30 Aug", open: 4, remediated: 1 },
  { date: "31 Aug", open: 2, remediated: 3 },
];

describe("DashboardOverview", () => {
  it("states the empty case rather than drawing an empty chart", () => {
    render(<DashboardOverview metrics={emptyDashboardMetrics} trend={[]} distribution={[]} />);
    expect(screen.getByText("No trend data yet")).toBeInTheDocument();
    expect(screen.getByText("No findings to distribute")).toBeInTheDocument();
  });

  it("draws the burn-down once there is a series to draw", () => {
    const { container } = render(
      <DashboardOverview metrics={emptyDashboardMetrics} trend={trend} distribution={[]} />,
    );
    expect(screen.queryByText("No trend data yet")).not.toBeInTheDocument();
    expect(container.querySelector(".recharts-responsive-container")).not.toBeNull();
  });

  it("keeps decorative charts out of the accessibility tree", () => {
    const { container } = render(
      <DashboardOverview
        metrics={emptyDashboardMetrics}
        trend={trend}
        distribution={[{ severity: "high", count: 2 }]}
      />,
    );
    // The surrounding summary carries the numbers as text; the chart itself
    // must not enter keyboard navigation.
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0);
  });

  it("drops both chart cards before the first scan instead of repeating an empty state", () => {
    render(
      <DashboardOverview metrics={emptyDashboardMetrics} trend={[]} distribution={[]} hasScans={false} />,
    );
    expect(screen.queryByText("No trend data yet")).not.toBeInTheDocument();
    expect(screen.queryByText("No findings to distribute")).not.toBeInTheDocument();
    // The counters still stand: they are the honest zero, not an empty chart.
    expect(screen.getByText("AI Security Posture")).toBeInTheDocument();
  });

  it("shows a skeleton while loading rather than a misleading zero state", () => {
    render(<DashboardOverview metrics={emptyDashboardMetrics} trend={[]} distribution={[]} loading />);
    expect(screen.queryByText("No trend data yet")).not.toBeInTheDocument();
  });
});
