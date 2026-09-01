import { useEffect, useState } from "react";
import {
  Columns2,
  FileCode2,
  Rows2,
  Sparkles,
} from "lucide-react";
import type { Asset, Finding, FindingHistoryEntry } from "@/types";
import { statusStyles } from "@/lib/severity";
import { cn } from "@/lib/utils";
import { SeverityBadge } from "@/components/SeverityBadge";
import { RiskScoreBadge } from "@/components/RiskScoreBadge";
import { Button } from "@/components/ui/button";
import { VulnerableCodeBlock } from "./VulnerableCodeBlock";
import { RemediatedCodeBlock } from "./RemediatedCodeBlock";
import { FindingMarkdownReader } from "./FindingMarkdownReader";
import { TriageControl } from "./TriageControl";
import { RawEvidencePanel } from "./RawEvidencePanel";
import { apiPostOptional } from "@/lib/api";

interface AnalysisWorkspaceProps {
  finding: Finding;
  asset?: Asset;
  scanId?: string;
  history?: FindingHistoryEntry[];
  onMarkForReview: () => void;
  onChangeStatus?: (patch: Record<string, string>) => void;
}

function parseState(value: FindingHistoryEntry["new_state"]): Record<string, unknown> {
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value) as Record<string, unknown>;
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
      return {};
    }
  }
  return value || {};
}

export function AnalysisWorkspace({
  finding,
  asset,
  scanId,
  history = [],
  onMarkForReview,
  onChangeStatus,
}: AnalysisWorkspaceProps) {
  const [split, setSplit] = useState(true);
  const [aiExplanation, setAiExplanation] = useState<string | null>(null);
  const status = statusStyles[finding.status];
  const provenanceLabel = finding.source === "ai_assisted" ? "AI-assisted" : finding.source === "inferred" ? "Inferred" : "Observed";

  // Fetch a model-grounded explanation for the selected finding. Falls back
  // silently to the finding's own summary if the assistant is unavailable.
  useEffect(() => {
    let cancelled = false;
    setAiExplanation(null);
    (async () => {
      try {
        const data = await apiPostOptional<{ explanation?: string; backend?: string }>("/api/assistant/explain", {
          finding: {
            title: finding.title,
            severity: finding.severity,
            status: finding.status,
            affected_component: finding.affectedPath,
            recommendation: finding.remediation?.summary,
          },
        });
        if (!data || cancelled) return;
        if (!cancelled && data.explanation && data.backend?.startsWith("local-model")) {
          setAiExplanation(data.explanation);
        }
      } catch {
        /* assistant optional; keep the finding's own summary */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [finding.id, finding.title, finding.affectedPath, finding.severity, finding.status, finding.remediation?.summary]);

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge severity={finding.severity} withIcon />
          <RiskScoreBadge score={finding.riskScore} size="md" />
          <span className="inline-flex items-center rounded-sm border border-border bg-muted px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-muted-foreground" title={`Provenance: ${provenanceLabel.toLowerCase()} · ${finding.tool} · ${finding.confidence} confidence`}>
            {provenanceLabel}
          </span>
          <span
            className={cn(
              "inline-flex items-center rounded-sm border px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide",
              status.className,
            )}
          >
            {status.label}
          </span>
        </div>

        <h2 className="mt-2.5 font-sans text-lg font-extrabold leading-tight tracking-tight text-foreground">
          {finding.title}
        </h2>

        <p className="mt-1 flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
          <FileCode2 className="size-3.5" />
          {asset ? `${asset.name} · ` : ""}
          {finding.affectedPath}
        </p>

        {onChangeStatus ? <TriageControl status={finding.status} onChange={onChangeStatus} /> : null}

        <div className="mt-3 flex gap-2 rounded-md border border-border bg-[color-mix(in_srgb,var(--accent-slate)_8%,transparent)] p-3">
          <Sparkles className="mt-0.5 size-4 shrink-0 text-[var(--accent-slate)]" />
          <p className="text-sm leading-relaxed text-foreground">
            <span className="font-semibold">Finding explanation · </span>
            {aiExplanation ?? finding.aiSummary}
            {aiExplanation ? (
              <span className="ml-1 rounded bg-[var(--accent-slate)]/15 px-1 text-[10px] font-semibold uppercase text-[var(--accent-slate)]">
                AI
              </span>
            ) : null}
          </p>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">{finding.tool} · {finding.confidence} confidence{finding.observedAt ? ` · observed ${new Date(finding.observedAt).toLocaleString()}` : ""}</p>
      </header>

      <div className="flex-1 overflow-y-auto scrollbar-thin p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
            Mitigation View
          </h2>
          <div className="hidden items-center gap-1 rounded-md border border-border bg-muted p-0.5 lg:flex">
            <Button
              variant={split ? "primary" : "ghost"}
              size="sm"
              className="h-7"
              onClick={() => setSplit(true)}
              aria-pressed={split}
            >
              <Columns2 className="size-3.5" /> Split
            </Button>
            <Button
              variant={!split ? "primary" : "ghost"}
              size="sm"
              className="h-7"
              onClick={() => setSplit(false)}
              aria-pressed={!split}
            >
              <Rows2 className="size-3.5" /> Stacked
            </Button>
          </div>
        </div>

        <div
          className={cn(
            "grid gap-4",
            split ? "lg:grid-cols-2" : "grid-cols-1",
          )}
        >
          <VulnerableCodeBlock block={finding.vulnerableCode} />
          <RemediatedCodeBlock
            remediation={finding.remediation}
            onMarkForReview={onMarkForReview}
          />
        </div>

        <div className="mt-4">
          <FindingMarkdownReader sections={finding.report} />
        </div>

        {scanId ? <RawEvidencePanel scanId={scanId} findingId={finding.id} /> : null}

        {history.length ? (
          <section className="mt-4 rounded-lg border border-border bg-card p-3 shadow-card">
            <h2 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Persisted finding history</h2>
            <ol className="mt-3 space-y-2 text-xs text-muted-foreground">
              {history.slice(-6).map((entry, index) => {
                const state = parseState(entry.new_state);
                return (
                  <li key={`${entry.id || index}-${entry.timestamp}`} className="rounded-md border border-border bg-muted p-2">
                    <p className="font-semibold text-foreground">
                      {String(state.status || "updated")} by {entry.actor || "unknown"}
                    </p>
                    <p>{entry.timestamp}</p>
                    {entry.note ? <p className="mt-1">{entry.note}</p> : null}
                  </li>
                );
              })}
            </ol>
          </section>
        ) : null}
      </div>
    </div>
  );
}
