import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import type { FindingStatus } from "@/types";
import { Button } from "@/components/ui/button";

/** Statuses a reviewer can set. Matches what the backend accepts. */
const TRIAGE_STATUSES: { value: FindingStatus; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "triaged", label: "Triaged" },
  { value: "in_progress", label: "In progress" },
  { value: "accepted_risk", label: "Accepted risk" },
  { value: "false_positive", label: "False positive" },
  { value: "fixed", label: "Fixed" },
  { value: "wont_fix", label: "Won't fix" },
];

/** The backend refuses these without a recorded justification. */
const REASON_FIELD: Partial<Record<FindingStatus, "accepted_risk_reason" | "false_positive_reason">> = {
  accepted_risk: "accepted_risk_reason",
  false_positive: "false_positive_reason",
};

interface TriageControlProps {
  status: FindingStatus;
  busy?: boolean;
  onChange: (patch: Record<string, string>) => void;
}

/**
 * Set a finding's review status.
 *
 * Accepting a risk or dismissing a finding as a false positive both require a
 * written reason — the backend rejects them without one — so the control asks
 * for it before submitting rather than letting the request fail.
 */
export function TriageControl({ status, busy = false, onChange }: TriageControlProps) {
  const [pending, setPending] = useState<FindingStatus | null>(null);
  const [reason, setReason] = useState("");

  const reasonField = pending ? REASON_FIELD[pending] : undefined;

  function select(next: FindingStatus) {
    if (next === status) return;
    if (REASON_FIELD[next]) {
      setPending(next);
      setReason("");
      return;
    }
    onChange({ status: next });
  }

  function confirm() {
    if (!pending || !reasonField || !reason.trim()) return;
    onChange({ status: pending, [reasonField]: reason.trim() });
    setPending(null);
    setReason("");
  }

  return (
    <div className="ui-action-row mt-3 flex flex-wrap items-center gap-2">
      <label className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-muted-foreground">
        <ShieldCheck className="ui-icon size-3.5" />
        Review status
      </label>
      <select
        aria-label="Finding review status"
        value={pending ?? status}
        disabled={busy}
        onChange={(event) => select(event.target.value as FindingStatus)}
        className="min-w-0 rounded-sm border border-border bg-card px-2 py-1 text-xs font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
      >
        {TRIAGE_STATUSES.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      {pending && reasonField ? (
        <div className="flex w-full flex-wrap items-center gap-2">
          <input
            type="text"
            autoFocus
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") confirm();
              if (event.key === "Escape") setPending(null);
            }}
            placeholder={
              pending === "accepted_risk"
                ? "Why is this risk being accepted?"
                : "Why is this not a real finding?"
            }
            aria-label="Reason"
            className="min-w-0 flex-1 rounded-sm border border-border bg-card px-2 py-1 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <Button size="sm" variant="primary" disabled={!reason.trim() || busy} onClick={confirm}>
            Record
          </Button>
          <Button size="sm" variant="outline" onClick={() => setPending(null)}>
            Cancel
          </Button>
          <p className="w-full break-anywhere text-[11px] text-muted-foreground">
            A reason is required and is kept in the finding&apos;s audit history.
          </p>
        </div>
      ) : null}
    </div>
  );
}
