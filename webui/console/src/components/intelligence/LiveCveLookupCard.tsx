import { useEffect, useState } from "react";
import { DatabaseZap, ExternalLink, Loader2, ShieldAlert } from "lucide-react";
import type { Finding } from "@/types";
import { apiPostOptional } from "@/lib/api";

interface CveMatch {
  id: string;
  source: string;
  summary: string;
  severity?: string;
  url: string;
}

interface CveLookupResult {
  query: string;
  matches: CveMatch[];
  match_count: number;
  candidate_novel: boolean;
  online: boolean;
  note: string;
  sources_queried: string[];
}

export function LiveCveLookupCard({ finding }: { finding: Finding }) {
  const [result, setResult] = useState<CveLookupResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setResult(null);
    setLoading(true);
    (async () => {
      try {
        const data = await apiPostOptional<CveLookupResult>("/api/findings/cve", {
          finding: {
            title: finding.title,
            category: finding.cwe?.id,
            affected_component: finding.affectedPath,
          },
        });
        if (data && !cancelled) setResult(data);
      } catch {
        /* online lookup is optional */
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [finding.id, finding.title, finding.affectedPath, finding.cwe?.id]);

  return (
    <section className="rounded-lg border border-border bg-card p-3 shadow-card">
      <header className="mb-2 flex items-center gap-2">
        <DatabaseZap className="size-4 text-[var(--accent-slate)]" />
        <h3 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
          CVE correlation (NVD / OSV)
        </h3>
        {loading ? <Loader2 className="size-3.5 animate-spin text-muted-foreground" /> : null}
      </header>

      {!result && !loading ? (
        <p className="text-xs text-muted-foreground">Online lookup unavailable.</p>
      ) : null}

      {result ? (
        <div className="space-y-2">
          {result.candidate_novel ? (
            <div className="flex items-start gap-2 rounded-md border border-severity-medium/40 bg-severity-medium/10 p-2">
              <ShieldAlert className="mt-0.5 size-4 shrink-0 text-severity-medium" />
              <p className="text-xs text-foreground">
                No public CVE matched — possible novel/zero-day. Requires human verification.
              </p>
            </div>
          ) : null}

          {result.matches.length ? (
            <ul className="space-y-1.5">
              {result.matches.slice(0, 6).map((m) => (
                <li key={`${m.source}-${m.id}`} className="rounded-md border border-border bg-muted p-2">
                  <a
                    href={m.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-xs font-bold text-[var(--accent-slate)] hover:underline"
                  >
                    {m.id} <ExternalLink className="size-3" />
                  </a>
                  <span className="ml-2 rounded bg-card px-1 text-[10px] text-muted-foreground">{m.source}</span>
                  {m.severity ? <span className="ml-1 text-[10px] text-muted-foreground">· {m.severity}</span> : null}
                  <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">{m.summary}</p>
                </li>
              ))}
            </ul>
          ) : null}

          <p className="text-[11px] italic text-muted-foreground">{result.note}</p>
        </div>
      ) : null}
    </section>
  );
}
