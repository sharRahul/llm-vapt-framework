import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { SeverityDistributionPoint } from "@/types";
import { severityStyles } from "@/lib/severity";
import { ChartTooltip } from "./ChartTooltip";

export function SeverityDonutChart({
  data,
}: {
  data: SeverityDistributionPoint[];
}) {
  const total = data.reduce((sum, d) => sum + d.count, 0);
  const chartData = data.map((d) => ({
    name: severityStyles[d.severity].label,
    value: d.count,
    fill: severityStyles[d.severity].cssVar,
  }));

  return (
    <div className="flex h-full items-center gap-4">
      <div className="relative h-[150px] w-[150px] shrink-0" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart accessibilityLayer={false}>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              innerRadius={48}
              outerRadius={70}
              paddingAngle={2}
              stroke="var(--card)"
              strokeWidth={2}
            >
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-sans text-2xl font-extrabold leading-none tabular-nums text-foreground">
            {total}
          </span>
          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Findings
          </span>
        </div>
      </div>
      <ul className="flex-1 space-y-1.5">
        {data.map((d) => {
          const style = severityStyles[d.severity];
          const pct = total ? Math.round((d.count / total) * 100) : 0;
          return (
            <li key={d.severity} className="flex items-center gap-2 text-sm">
              <span
                className="size-2.5 rounded-sm"
                style={{ background: style.cssVar }}
              />
              <span className="font-medium text-foreground">{style.label}</span>
              <span className="ml-auto font-semibold tabular-nums text-muted-foreground">
                {d.count} · {pct}%
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
