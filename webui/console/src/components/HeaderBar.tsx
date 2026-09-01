import {
  Cpu,
  FolderOpen,
  LayoutDashboard,
  Loader2,
  Moon,
  PanelsTopLeft,
  Server,
  Play,
  Square,
  ShieldHalf,
  Sun,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ConsoleView = "overview" | "workspace" | "targets" | "agents" | "projects";

export interface HeaderBarProps {
  view: ConsoleView;
  onChangeView: (view: ConsoleView) => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  scanning: boolean;
  scanStatusLabel?: string;
  scanProgressPercent?: number;
  scanFindingCount?: number;
  scanDisabled?: boolean;
  onToggleScan: () => void;
  onCancelScan?: () => void;
  cancelling?: boolean;
  targets?: { id: string; label: string; ready?: boolean }[];
  selectedTarget?: string;
  onSelectTarget?: (id: string) => void;
}

export function HeaderBar({
  view,
  onChangeView,
  theme,
  onToggleTheme,
  scanning,
  scanStatusLabel,
  scanProgressPercent = 0,
  scanFindingCount = 0,
  scanDisabled = false,
  onToggleScan,
  onCancelScan,
  cancelling = false,
  targets = [],
  selectedTarget = "",
  onSelectTarget,
}: HeaderBarProps) {
  const scanLabel = scanning
    ? `${scanStatusLabel || "Scan running"} · ${Math.round(scanProgressPercent)}% · ${scanFindingCount} findings`
    : "Idle";

  return (
    <header className="relative flex min-h-14 shrink-0 flex-wrap items-center gap-2 border-b border-border bg-card px-3 py-2 sm:gap-3 sm:px-4">
      <div className="ui-title-row min-w-[150px] shrink-0">
        <span className="ui-icon size-8 rounded-md bg-primary text-primary-foreground">
          <ShieldHalf className="size-5" />
        </span>
        <div className="min-w-0 leading-none">
          {/* The console needs exactly one top-level heading; without it the
              page has no h1 for screen readers or document outline. */}
          <h1 className="truncate font-sans text-sm font-extrabold tracking-tight text-foreground">
            VulnoraIQ
          </h1>
          <p className="hidden truncate text-[10px] font-medium uppercase tracking-wide text-muted-foreground sm:block">
            AI Security Operations
          </p>
        </div>
      </div>

      <nav className="order-3 flex max-w-full items-center gap-1 overflow-x-auto rounded-md border border-border bg-muted p-0.5 scrollbar-thin sm:order-none sm:ml-2" aria-label="Console views">
        <ViewTab
          active={view === "overview"}
          onClick={() => onChangeView("overview")}
          icon={<LayoutDashboard className="size-4" />}
          label="Overview"
        />
        <ViewTab
          active={view === "workspace"}
          onClick={() => onChangeView("workspace")}
          icon={<PanelsTopLeft className="size-4" />}
          label="Workspace"
        />
        <ViewTab
          active={view === "targets"}
          onClick={() => onChangeView("targets")}
          icon={<Server className="size-4" />}
          label="Targets"
        />
        <ViewTab
          active={view === "agents"}
          onClick={() => onChangeView("agents")}
          icon={<Cpu className="size-4" />}
          label="Agents"
        />
        <ViewTab
          active={view === "projects"}
          onClick={() => onChangeView("projects")}
          icon={<FolderOpen className="size-4" />}
          label="Projects"
        />
      </nav>

      <div className="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-2">
        <span className="hidden max-w-[340px] items-center gap-1.5 rounded-md border border-border bg-canvas px-2 py-1 text-[11px] font-semibold text-muted-foreground md:inline-flex">
          <span
            className={cn(
              "size-1.5 shrink-0 rounded-full",
              scanning ? "animate-pulse bg-[var(--accent-sage)]" : "bg-muted-foreground opacity-50",
            )}
          />
          <span className="truncate">{scanLabel}</span>
        </span>

        {/* The selector was hidden below the `sm` breakpoint while Run Scan
            stayed enabled, so a phone-sized operator could start a scan against
            a target they could not see. It shrinks instead of hiding. */}
        {targets.length > 0 ? (
          <label className="inline-flex items-center gap-1.5" title="Target to scan">
            <span className="sr-only">Target to scan</span>
            <select
              value={selectedTarget}
              onChange={(e) => onSelectTarget?.(e.target.value)}
              disabled={scanning}
              className="input h-8 max-w-[130px] py-0 text-xs sm:max-w-[200px]"
              aria-label="Target to scan"
            >
              {targets.map((t) => (
                <option key={t.id} value={t.id} disabled={t.ready === false}>{t.label}{t.ready === false ? " · unavailable" : ""}</option>
              ))}
            </select>
          </label>
        ) : null}

        {scanning && onCancelScan ? (
          // Stopping traffic to a target is a safety control, so the control is
          // reachable for as long as the run is not finished.
          <Button variant="secondary" size="sm" onClick={onCancelScan} disabled={cancelling} className="shrink-0" title="Stop this scan">
            <Square className="size-4" /> <span>{cancelling ? "Stopping…" : "Stop"}</span>
          </Button>
        ) : null}

        <Button variant="primary" size="sm" onClick={onToggleScan} disabled={scanning || scanDisabled} className="shrink-0" title={scanDisabled ? "No targets configured. Add a target in the Targets view first." : "Run a scan"}>
          {scanning ? (
            <>
              <Loader2 className="size-4 animate-spin" /> <span>Scanning…</span>
            </>
          ) : (
            <>
              <Play className="size-4" /> <span>Run Scan</span>
            </>
          )}
        </Button>

        <Button
          variant="secondary"
          size="icon"
          onClick={onToggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </Button>
      </div>
      {scanning && (
        <div className="absolute bottom-0 left-0 right-0 h-[2px] overflow-hidden bg-border">
          <div
            className="h-full bg-[var(--accent-sage)] transition-[width] duration-500 ease-out"
            style={{ width: `${Math.max(scanProgressPercent, 3)}%` }}
          />
        </div>
      )}
    </header>
  );
}

function ViewTab({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
      className={cn(
        "inline-flex shrink-0 items-center justify-center gap-1.5 rounded px-2.5 py-1.5 text-xs font-semibold leading-none transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "bg-card text-foreground shadow-card"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      <span className="ui-icon">{icon}</span>
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}
