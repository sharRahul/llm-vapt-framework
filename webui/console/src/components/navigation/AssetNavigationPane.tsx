import { useEffect, useMemo, useState } from "react";
import { Layers, Search, X } from "lucide-react";
import type { Asset, Finding } from "@/types";
import { SEVERITY_ORDER } from "@/lib/severity";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/EmptyState";
import { AssetFindingCard } from "./AssetFindingCard";

type SortKey = "risk" | "severity" | "type";

interface AssetNavigationPaneProps {
  assets: Asset[];
  findingsById: Record<string, Finding>;
  selectedFindingId: string | null;
  onSelectFinding: (findingId: string) => void;
}

const sortLabels: Record<SortKey, string> = {
  risk: "Risk score",
  severity: "Severity",
  type: "Asset type",
};

export function AssetNavigationPane({
  assets,
  findingsById,
  selectedFindingId,
  onSelectFinding,
}: AssetNavigationPaneProps) {
  const [sort, setSort] = useState<SortKey>("risk");
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => {
    const first = assets[0]?.id;
    return first ? { [first]: true } : {};
  });

  // Scan data is loaded after this pane mounts. Expand the first asset once it
  // arrives, without reopening an asset the operator explicitly collapsed.
  useEffect(() => {
    setExpanded((previous) => {
      if (Object.keys(previous).length || !assets[0]?.id) return previous;
      return { [assets[0].id]: true };
    });
  }, [assets]);

  const visibleAssets = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? assets.filter(
          (a) =>
            a.name.toLowerCase().includes(q) ||
            a.locator.toLowerCase().includes(q),
        )
      : assets;
    const sorted = [...filtered].sort((a, b) => {
      if (sort === "risk") return b.riskScore - a.riskScore;
      if (sort === "severity")
        return (
          SEVERITY_ORDER[b.highestSeverity] - SEVERITY_ORDER[a.highestSeverity]
        );
      return a.type.localeCompare(b.type);
    });
    return sorted;
  }, [assets, query, sort]);

  return (
    <div className="flex h-full flex-col">
      <div className="space-y-2.5 border-b border-border p-3">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-muted-foreground">
            <Layers className="size-3.5" />
            Scanned Assets
          </h2>
          <span className="rounded-sm bg-muted px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-muted-foreground">
            {visibleAssets.length}
          </span>
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter assets…"
            aria-label="Filter assets"
            className={cn(
              "h-8 w-full rounded-md border border-border bg-canvas pl-8 text-xs text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              query ? "pr-7" : "pr-2",
            )}
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              aria-label="Clear filter"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="size-3.5" />
            </button>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-medium text-muted-foreground">Sort</span>
          <div className="flex gap-1" role="group" aria-label="Sort assets">
            {(Object.keys(sortLabels) as SortKey[]).map((key) => (
              <button
                key={key}
                onClick={() => setSort(key)}
                aria-pressed={sort === key}
                className={cn(
                  "rounded-sm border px-2 py-1 text-[11px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  sort === key
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {sortLabels[key]}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto scrollbar-thin p-3">
        {visibleAssets.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No assets match"
            description="Adjust your filter to see scanned assets."
          />
        ) : (
          visibleAssets.map((asset) => (
            <AssetFindingCard
              key={asset.id}
              asset={asset}
              findings={asset.findingIds.map((id) => findingsById[id]).filter(Boolean)}
              expanded={!!expanded[asset.id]}
              selectedFindingId={selectedFindingId}
              onToggle={() =>
                setExpanded((prev) => ({ ...prev, [asset.id]: !prev[asset.id] }))
              }
              onSelectFinding={onSelectFinding}
            />
          ))
        )}
      </div>
    </div>
  );
}
