import { Crosshair, Layers3, ScrollText, ShieldCheck } from "lucide-react";
import type { IntelligenceMapping } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SeverityBadge } from "@/components/SeverityBadge";
import { cn } from "@/lib/utils";

const exploitabilityLabel: Record<IntelligenceMapping["exploitability"], string> = {
  theoretical: "Theoretical",
  poc: "Proof of Concept",
  functional: "Functional",
  active: "Actively Exploited",
};

const policyTone: Record<IntelligenceMapping["policyStatus"], string> = {
  pass: "text-severity-low border-severity-low",
  warn: "text-severity-medium border-severity-medium",
  fail: "text-severity-high border-severity-high",
  manual_review: "text-[var(--accent-slate)] border-slate",
};

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <span className="text-right text-sm font-semibold text-foreground">{children}</span>
    </div>
  );
}

export function IntelligenceMappingCard({
  mapping,
}: {
  mapping: IntelligenceMapping;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Layers3 className="size-4 text-[var(--accent-slate)]" />
          Classification & Mapping
        </CardTitle>
      </CardHeader>
      <CardContent className="divide-y divide-border">
        {mapping.owaspLlm && (
          <Row label="OWASP LLM Top 10">
            <span className="inline-flex items-center gap-1">
              <ScrollText className="size-3.5 text-muted-foreground" />
              {mapping.owaspLlm}
            </span>
          </Row>
        )}
        {mapping.mitreAtlas && (
          <Row label="MITRE ATLAS">
            <span className="inline-flex items-center gap-1">
              <Crosshair className="size-3.5 text-muted-foreground" />
              {mapping.mitreAtlas}
            </span>
          </Row>
        )}
        <Row label="Exploitability">{exploitabilityLabel[mapping.exploitability]}</Row>
        <Row label="Affected component">{mapping.affectedComponent}</Row>
        <Row label="Recommended priority">
          <SeverityBadge severity={mapping.recommendedPriority} />
        </Row>
        <Row label="Policy status">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-[11px] font-bold uppercase",
              policyTone[mapping.policyStatus],
            )}
          >
            <ShieldCheck className="size-3" />
            {mapping.policyStatus.replace("_", " ")}
          </span>
        </Row>
        {/* A "Compliance" heading over nothing is a row that says nothing. */}
        {mapping.complianceTags.length ? (
          <div className="pt-2">
            <span className="text-xs font-medium text-muted-foreground">Compliance</span>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {mapping.complianceTags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-sm border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] font-semibold text-foreground"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
