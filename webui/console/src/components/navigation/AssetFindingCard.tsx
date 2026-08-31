import { AlertTriangle, ChevronRight, Clock } from "lucide-react";
import type { Asset, Finding } from "@/types";
import { assetTypeMeta } from "@/lib/assets";
import { severityStyles } from "@/lib/severity";
import { cn, formatRelativeTime } from "@/lib/utils";
import { SeverityBadge } from "@/components/SeverityBadge";
import { RiskScoreBadge } from "@/components/RiskScoreBadge";

interface AssetFindingCardProps {
  asset: Asset;
  findings: Finding[];
  expanded: boolean;
  selectedFindingId: string | null;
  onToggle: () => void;
  onSelectFinding: (findingId: string) => void;
}

export function AssetFindingCard({
  asset,
  findings,
  expanded,
  selectedFindingId,
  onToggle,
  onSelectFinding,
}: AssetFindingCardProps) {
  const meta = assetTypeMeta[asset.type];
  const Icon = meta.icon;
  const failed = asset.scanStatus === "failed";

  return (
    <div className="rounded-md border border-border bg-card shadow-card transition-shadow hover:shadow-card-hover">
      <button
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-start gap-2.5 rounded-md p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="ui-icon mt-0.5 size-7 rounded-md border border-border bg-muted text-[var(--accent-slate)]">
          <Icon className="size-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex min-w-0 items-start gap-1.5">
            <span className="break-anywhere text-sm font-bold leading-snug text-foreground">
              {asset.name}
            </span>
            <ChevronRight
              className={cn(
                "ml-auto size-4 shrink-0 text-muted-foreground transition-transform",
                expanded && "rotate-90",
              )}
            />
          </span>
          <span className="mt-0.5 block truncate font-mono text-[11px] text-muted-foreground" title={asset.locator}>
            {asset.locator}
          </span>
          <span className="mt-2 flex flex-wrap items-center gap-1.5">
            {failed ? (
              // A scan that never ran produced no evidence. Showing it as
              // "info / 0 vulns" would read as a clean result.
              <span className="inline-flex items-center gap-1 rounded-sm border border-[var(--sev-high)] bg-[var(--sev-high)]/10 px-1.5 py-0.5 text-[11px] font-bold text-[var(--sev-high)]">
                <AlertTriangle className="size-3 shrink-0" />
                Scan failed
              </span>
            ) : (
              <>
                <SeverityBadge severity={asset.highestSeverity} />
                <RiskScoreBadge score={asset.riskScore} />
                <span className="inline-flex items-center rounded-sm border border-border bg-muted px-1.5 py-0.5 text-[11px] font-semibold text-muted-foreground">
                  {asset.vulnerabilityCount} {asset.vulnerabilityCount === 1 ? "vuln" : "vulns"}
                </span>
              </>
            )}
          </span>
          {failed && asset.scanError ? (
            <span className="mt-1.5 block break-anywhere text-[11px] font-medium text-[var(--sev-high)]" title={asset.scanError}>
              {asset.scanError}
            </span>
          ) : null}
          <span className="mt-1.5 flex min-w-0 items-center gap-1 text-[11px] text-muted-foreground">
            <Clock className="size-3 shrink-0" />
            <span className="truncate">{meta.label} · scanned {formatRelativeTime(asset.lastScanned)}</span>
          </span>
        </span>
      </button>

      {expanded && findings.length > 0 && (
        <ul className="border-t border-border p-1.5">
          {findings.map((f) => {
            const selected = f.id === selectedFindingId;
            const style = severityStyles[f.severity];
            return (
              <li key={f.id}>
                <button
                  onClick={() => onSelectFinding(f.id)}
                  aria-current={selected}
                  className={cn(
                    "group flex w-full items-center gap-2 rounded px-2 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    selected
                      ? "bg-muted shadow-[inset_2px_0_0_0_var(--ring)]"
                      : "hover:bg-muted",
                  )}
                >
                  <span
                    className={cn(
                      "shrink-0 self-stretch rounded-full transition-all duration-200",
                      selected ? "w-[3px]" : "w-1 opacity-50 group-hover:opacity-90",
                    )}
                    style={{ background: style.cssVar }}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="line-clamp-2 text-xs font-semibold leading-snug text-foreground">
                      {f.title}
                    </span>
                    <span className="mt-0.5 block truncate font-mono text-[10px] text-muted-foreground" title={f.affectedPath}>
                      {f.affectedPath}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
