import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { VulnerabilityTrendPoint } from "@/types";
import { ChartTooltip } from "./ChartTooltip";

export function BurnDownChart({ data }: { data: VulnerabilityTrendPoint[] }) {
  return (
    <div className="h-full w-full" aria-hidden="true">
      <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }} accessibilityLayer={false}>
        <defs>
          <linearGradient id="grad-open" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--sev-high)" stopOpacity={0.28} />
            <stop offset="100%" stopColor="var(--sev-high)" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="grad-remediated" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent-sage)" stopOpacity={0.26} />
            <stop offset="100%" stopColor="var(--accent-sage)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
          tickLine={false}
          axisLine={{ stroke: "var(--border)" }}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
          tickLine={false}
          axisLine={false}
          width={40}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--border)" }} />
        <Area
          type="monotone"
          dataKey="open"
          name="Open"
          stroke="var(--sev-high)"
          strokeWidth={2}
          fill="url(#grad-open)"
        />
        <Area
          type="monotone"
          dataKey="remediated"
          name="Remediated"
          stroke="var(--accent-sage)"
          strokeWidth={2}
          fill="url(#grad-remediated)"
        />
      </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
