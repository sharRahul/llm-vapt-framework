import { useEffect, useRef, useState } from "react";
import { ChevronRight, FileSearch, Loader2 } from "lucide-react";
import type { EvidenceArtifact, EvidenceEntry } from "@/types";
import { apiGet } from "@/lib/api";
import { cn } from "@/lib/utils";

interface RawEvidencePanelProps {
  scanId: string;
  findingId: string;
}

/**
 * The raw request/response evidence a scan wrote to disk.
 *
 * Evidence was written and never read back — no index, no route, no link from a
 * finding — so the material a reviewer most wants was the least reachable. It
 * is collapsed by default because it is reference material, not the summary.
 */
export function RawEvidencePanel({ scanId, findingId }: RawEvidencePanelProps) {
  const [open, setOpen] = useState(false);
  const [entry, setEntry] = useState<EvidenceEntry | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [artifact, setArtifact] = useState<{ id: string; content: unknown } | null>(null);

  // Which finding the panel has already requested. Tracking this in a ref
  // rather than a state dependency matters: `loading` in the dependency list
  // made the effect tear down its own in-flight request the moment it started,
  // leaving the panel on "Loading evidence…" forever.
  const requestedFor = useRef<string | null>(null);
  const key = `${scanId}/${findingId}`;

  useEffect(() => {
    requestedFor.current = null;
    setEntry(null);
    setArtifact(null);
    setError(null);
    setLoading(false);
  }, [key]);

  useEffect(() => {
    if (!open || requestedFor.current === key) return;
    requestedFor.current = key;
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const data = await apiGet<{ evidence: EvidenceEntry }>(
          `/api/scans/${encodeURIComponent(scanId)}/evidence/${encodeURIComponent(findingId)}`,
        );
        if (!cancelled) setEntry(data.evidence);
      } catch (exc) {
        if (!cancelled) setError(exc instanceof Error ? exc.message : String(exc));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, key, scanId, findingId]);

  async function openArtifact(item: EvidenceArtifact): Promise<void> {
    if (artifact?.id === item.artifact_id) {
      setArtifact(null);
      return;
    }
    try {
      const data = await apiGet<{ evidence: { content: unknown } }>(
        `/api/scans/${encodeURIComponent(scanId)}/evidence/${encodeURIComponent(findingId)}/${encodeURIComponent(item.artifact_id)}`,
      );
      setArtifact({ id: item.artifact_id, content: data.evidence.content });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  return (
    <section className="mt-4 rounded-lg border border-border bg-card shadow-card">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-lg p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <FileSearch className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Raw evidence</span>
        <ChevronRight className={cn("ml-auto size-4 text-muted-foreground transition-transform", open && "rotate-90")} />
      </button>

      {open ? (
        <div className="border-t border-border p-3 text-xs text-muted-foreground">
          {loading ? (
            <p className="flex items-center gap-1.5">
              <Loader2 className="size-3.5 animate-spin" /> Loading evidence…
            </p>
          ) : error ? (
            <p className="text-severity-high">{error}</p>
          ) : !entry?.artifacts?.length ? (
            <p>No raw evidence artefacts were recorded for this finding.</p>
          ) : (
            <ul className="space-y-1.5">
              {entry.artifacts.map((item) => (
                <li key={item.artifact_id} className="rounded-md border border-border bg-muted">
                  <button
                    type="button"
                    onClick={() => void openArtifact(item)}
                    disabled={item.available === false}
                    aria-expanded={artifact?.id === item.artifact_id}
                    className="flex w-full items-center gap-2 p-2 text-left font-mono text-[11px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                  >
                    <span className="truncate text-foreground">{item.name}</span>
                    <span className="ml-auto shrink-0 tabular-nums">{item.policy_decision}</span>
                  </button>
                  {artifact?.id === item.artifact_id ? (
                    <pre className="max-h-64 overflow-auto scrollbar-thin border-t border-border p-2 font-mono text-[11px] leading-relaxed text-foreground">
                      {JSON.stringify(artifact.content, null, 2)}
                    </pre>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </section>
  );
}
