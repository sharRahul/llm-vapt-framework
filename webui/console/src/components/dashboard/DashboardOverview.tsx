import { PieChart, TrendingDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  DashboardMetrics,
  SeverityDistributionPoint,
  VulnerabilityTrendPoint,
} from "@/types";
import { BurnDownChart } from "./BurnDownChart";
import { KpiGrid } from "./KpiGrid";
import { SeverityDonutChart } from "./SeverityDonutChart";
import { SkeletonDashboard } from "./SkeletonDashboard";

function ChartEmpty({
  icon: Icon,
  message,
  hint,
}: {
  icon: typeof PieChart;
  message: string;
  hint: string;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <span className="ui-icon size-10 rounded-lg bg-muted text-muted-foreground">
        <Icon className="size-5" />
      </span>
      <p className="text-sm font-semibold text-foreground">{message}</p>
      <p className="max-w-[15rem] text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

interface DashboardOverviewProps {
  metrics: DashboardMetrics;
  trend: VulnerabilityTrendPoint[];
  distribution: SeverityDistributionPoint[];
  loading?: boolean;
  /** False before the first scan, when the charts have nothing to say. */
  hasScans?: boolean;
}

export function DashboardOverview({
  metrics,
  trend,
  distribution,
  loading = false,
  hasScans = true,
}: DashboardOverviewProps) {
  if (loading) return <SkeletonDashboard />;

  return (
    <div className="space-y-4 animate-fade-in">
      <h2 className="font-sans text-lg font-extrabold tracking-tight text-foreground">
        AI Security Posture
      </h2>

      <KpiGrid metrics={metrics} />

      {/* Before the first scan both charts can only say they are empty, and
          the view already carries one "no scans yet" call to action. Two more
          empty cards would say the same thing twice more. */}
      {!hasScans ? null : (
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <TrendingDown className="size-4 text-[var(--accent-slate)]" />
              Vulnerability Burn-down Rate
            </CardTitle>
            <span className="text-xs text-muted-foreground">Last 7 days</span>
          </CardHeader>
          <CardContent>
            <div className="h-[220px] w-full">
              {trend.length ? (
                <BurnDownChart data={trend} />
              ) : (
                <ChartEmpty
                  icon={TrendingDown}
                  message="No trend data yet"
                  hint="Chart appears once scans accumulate."
                />
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PieChart className="size-4 text-[var(--accent-slate)]" />
              Severity Distribution
            </CardTitle>
          </CardHeader>
          <CardContent className="h-[220px]">
            {distribution.length ? (
              <SeverityDonutChart data={distribution} />
            ) : (
              <ChartEmpty
                icon={PieChart}
                message="No findings to distribute"
                hint="Appears once a scan returns findings."
              />
            )}
          </CardContent>
        </Card>
      </div>
      )}
    </div>
  );
}
