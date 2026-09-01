import { useEffect, useMemo, useRef, useState } from "react";
import { MousePointerSquareDashed, Play, ScanSearch, Server } from "lucide-react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider, useToast } from "@/components/ui/toast";
import { AppShell } from "@/components/AppShell";
import type { ConsoleView } from "@/components/HeaderBar";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { EmptyState } from "@/components/EmptyState";
import { DashboardOverview } from "@/components/dashboard/DashboardOverview";
import { AssetNavigationPane } from "@/components/navigation/AssetNavigationPane";
import { AnalysisWorkspace } from "@/components/workspace/AnalysisWorkspace";
import { IntelligencePanel } from "@/components/intelligence/IntelligencePanel";
import { AgentHost } from "@/components/agents/AgentHost";
import { ProjectImporter } from "@/components/projects/ProjectImporter";
import { TargetsManager } from "@/components/targets/TargetsManager";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import { distributionFor, latestScan, metricsFor, scanAsset, toFinding, trendLabel } from "@/lib/findings";
import { useTheme } from "@/hooks/useTheme";
import { emptySeverityDistribution, emptyTrendData } from "@/data/cleanState";
import { phaseLabel, scanStateStyle } from "@/lib/scanState";
import type { BackendFinding, Finding, FindingHistoryEntry, FindingMutationState, ScanEvent, ScanJob, TargetConfig, VulnerabilityTrendPoint } from "@/types";

const SCAN_EVENT_TYPES = ["scan_queued", "scan_started", "target_validated", "phase_started", "check_started", "check_completed", "finding_created", "evidence_saved", "report_written", "scan_completed", "scan_failed", "heartbeat"];
const TREND_WINDOW_DAYS = 7;
const CONSOLE_VIEWS: ConsoleView[] = ["overview", "workspace", "targets", "agents", "projects"];

// Sync the active view with the URL hash (#/targets) so views are linkable and a
// refresh lands back on the same tab. Hash routing avoids any server-side route
// config and works regardless of the mount path.
function viewFromHash(): ConsoleView | null {
  const raw = window.location.hash.replace(/^#\/?/, "");
  return (CONSOLE_VIEWS as string[]).includes(raw) ? (raw as ConsoleView) : null;
}

function ConsoleInner() {
  const { theme, toggleTheme } = useTheme();
  const { notify } = useToast();
  const scanSourceRef = useRef<EventSource | null>(null);
  const [view, setView] = useState<ConsoleView>(() => viewFromHash() ?? "overview");
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [activeScan, setActiveScan] = useState<ScanJob | null>(null);
  const [runtimeFindings, setRuntimeFindings] = useState<Finding[]>([]);
  const [findingHistories, setFindingHistories] = useState<Record<string, FindingHistoryEntry[]>>({});
  const [liveScanEvents, setLiveScanEvents] = useState<ScanEvent[]>([]);
  const [scanProgressPercent, setScanProgressPercent] = useState(0);
  const [scanPhase, setScanPhase] = useState("Idle");
  const [liveFindingCount, setLiveFindingCount] = useState(0);
  const [configuredTargetIds, setConfiguredTargetIds] = useState<string[]>([]);
  const [configuredTargets, setConfiguredTargets] = useState<{ id: string; label: string; ready: boolean }[]>([]);
  const [scanTargetId, setScanTargetId] = useState<string>("");
  const [trend, setTrend] = useState<VulnerabilityTrendPoint[]>(emptyTrendData);

  const displayFindings = runtimeFindings;
  const displayAssets = activeScan ? [scanAsset(activeScan, runtimeFindings)] : [];
  const findingsById = useMemo<Record<string, Finding>>(() => Object.fromEntries(displayFindings.map((f) => [f.id, f])), [displayFindings]);
  const metrics = useMemo(() => metricsFor(runtimeFindings, activeScan), [runtimeFindings, activeScan]);
  const distribution = useMemo(() => distributionFor(runtimeFindings), [runtimeFindings]);
  const selectedFinding = selectedFindingId ? findingsById[selectedFindingId] : null;
  const selectedAsset = selectedFinding ? displayAssets.find((asset) => asset.id === selectedFinding.assetId) : undefined;
  const selectedFindingHistory = selectedFindingId ? findingHistories[selectedFindingId] || [] : [];

  useEffect(() => {
    void loadTargets();
    void loadExistingScanState();
    void loadTrend();
    return () => { scanSourceRef.current?.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep view <-> URL hash in sync for deep-linking and refresh stability.
  useEffect(() => {
    const onHash = () => { const next = viewFromHash(); if (next) setView(next); };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    const target = `#/${view}`;
    if (window.location.hash !== target) window.history.replaceState(null, "", target);
  }, [view]);

  async function loadTargets() {
    try {
      const data = await apiGet<{ targets: Record<string, TargetConfig>; readiness?: Record<string, { ready?: boolean }> }>("/api/targets");
      const ids = Object.keys(data.targets || {});
      const targets = ids.map((id) => ({ id, label: data.targets[id]?.name || id, ready: data.readiness?.[id]?.ready !== false }));
      const readyIds = targets.filter((target) => target.ready).map((target) => target.id);
      setConfiguredTargetIds(readyIds);
      setConfiguredTargets(targets);
      if (!scanTargetId || !readyIds.includes(scanTargetId)) setScanTargetId(readyIds[0] || "");
    } catch (exc) {
      // A failed request is not the same as an empty configuration: without
      // this the console told the operator to add a target they already had.
      notify(exc instanceof Error ? `Unable to load targets: ${exc.message}` : "Unable to load targets", "error");
    }
  }

  // The burn-down is a property of the whole scan history, not of the scan
  // currently open, so it is loaded separately and refreshed whenever a run
  // ends or a finding's status changes.
  async function loadTrend(): Promise<void> {
    try {
      const data = await apiGet<{ points: { date: string; open: number; remediated: number }[] }>(`/api/trends?days=${TREND_WINDOW_DAYS}`);
      setTrend((data.points || []).map((point) => ({ date: trendLabel(point.date), open: point.open, remediated: point.remediated })));
    } catch {
      // A missing trend is not worth a toast: the card states its own empty
      // case, and the operator has not asked for it.
      setTrend(emptyTrendData);
    }
  }

  async function refreshFindingHistory(scanId: string, findingId: string): Promise<void> {
    const data = await apiGet<{ history: FindingHistoryEntry[] }>(`/api/scans/${encodeURIComponent(scanId)}/findings/${encodeURIComponent(findingId)}/history`);
    setFindingHistories((prev) => ({ ...prev, [findingId]: data.history || [] }));
  }

  async function refreshScanFindings(scanId: string, scan?: ScanJob | null, preferredFindingId?: string, switchToWorkspace = true): Promise<void> {
    const findingsPayload = await apiGet<{ findings: BackendFinding[] }>(`/api/scans/${encodeURIComponent(scanId)}/findings`);
    const scanRecord = scan || activeScan || (await apiGet<ScanJob>(`/api/scans/${encodeURIComponent(scanId)}`));
    const nextFindings = (findingsPayload.findings || []).map((finding, index) => toFinding(finding, scanId, index));
    setActiveScan(scanRecord);
    void loadTrend();
    setRuntimeFindings(nextFindings);
    const nextSelected = nextFindings.find((finding) => finding.id === preferredFindingId) || nextFindings[0];
    setSelectedFindingId(nextSelected?.id || null);
    if (nextSelected) {
      // Only jump to the workspace on live completion / explicit selection —
      // never on initial load, so a deep-linked tab (#/projects, #/targets) is
      // preserved instead of being overridden by a saved scan.
      if (switchToWorkspace) setView("workspace");
      await refreshFindingHistory(scanId, nextSelected.id);
    }
  }

  async function loadExistingScanState(): Promise<void> {
    setDashboardLoading(true);
    try {
      const data = await apiGet<{ jobs: ScanJob[] }>("/api/scans");
      const scan = latestScan(data.jobs || []);
      if (scan) await refreshScanFindings(scan.id, scan, undefined, false);
      else {
        setActiveScan(null);
        setRuntimeFindings([]);
        setSelectedFindingId(null);
      }
    } catch (exc) {
      setActiveScan(null);
      setRuntimeFindings([]);
      setSelectedFindingId(null);
      notify(exc instanceof Error ? `Unable to load saved scans: ${exc.message}` : "Unable to load saved scans", "error");
    } finally {
      setDashboardLoading(false);
    }
  }

  function connectScanEvents(scan: ScanJob) {
    scanSourceRef.current?.close();
    setLiveScanEvents([]);
    setLiveFindingCount(0);
    setScanProgressPercent(0);
    setScanPhase("Queued");
    const source = new EventSource(`/api/scans/${encodeURIComponent(scan.id)}/events`, { withCredentials: true });
    scanSourceRef.current = source;
    const onEvent = (event: MessageEvent) => {
      const payload = JSON.parse(event.data) as ScanEvent;
      // Heartbeats keep the connection alive; they are not progress, and they
      // used to crowd every real step out of the visible timeline.
      if (payload.type !== "heartbeat") {
        setLiveScanEvents((prev) => {
          const next = [...prev.slice(-49), payload];
          setLiveFindingCount(next.filter((item) => item.type === "finding_created").length);
          return next;
        });
        setScanPhase(phaseLabel(payload.phase || payload.type));
      }
      setScanProgressPercent(payload.progress?.percent || 0);
      if (payload.type === "scan_completed" || payload.type === "scan_failed") {
        setScanning(false);
        setCancelling(false);
        setDashboardLoading(false);
        source.close();
        scanSourceRef.current = null;
        // Cancelled and timed-out runs share the terminal event type but are
        // not failures: the precise state travels in the event payload.
        const state = String(payload.data?.state || (payload.type === "scan_completed" ? "completed" : "failed"));
        const style = scanStateStyle(state);
        if (style.successful) {
          // Preserve the operator's current context. A completed scan must not
          // abruptly pull them away from the view they were using.
          void refreshScanFindings(scan.id, { ...scan, status: "completed" }, undefined, false);
        } else {
          // The backend reports why a scan ended; show that, not a generic message.
          const reason = payload.message || `Scan ${style.label.toLowerCase()}`;
          setActiveScan({ ...scan, status: state, error: reason });
          setScanPhase(`Scan ${style.label.toLowerCase()}`);
          notify(reason, state === "cancelled" ? "info" : "error");
        }
      }
    };
    SCAN_EVENT_TYPES.forEach((type) => source.addEventListener(type, onEvent));
    source.onerror = () => { if (scanSourceRef.current === source) setScanPhase("SSE connection interrupted"); };
  }

  async function handleToggleScan(explicitTarget?: string) {
    if (scanning) return;
    const targetId = explicitTarget || scanTargetId;
    setScanning(true);
    setCancelling(false);
    setDashboardLoading(true);
    setScanPhase("Creating scan");
    setScanProgressPercent(0);
    setLiveFindingCount(0);
    setRuntimeFindings([]);
    setFindingHistories({});
    setSelectedFindingId(null);
    try {
      if (!targetId) { notify("No targets configured. Add a target in the Targets view before running a scan.", "error"); setScanning(false); setDashboardLoading(false); return; }
      if (explicitTarget) setScanTargetId(explicitTarget);
      const job = await apiPost<ScanJob>("/api/scans", { target: targetId, profile: "baseline", authorised: true });
      setActiveScan(job);
      notify(`Scan ${job.id} queued — streaming live backend progress`, "info");
      connectScanEvents(job);
    } catch (exc) {
      setScanning(false);
      setDashboardLoading(false);
      setScanPhase("Scan start failed");
      notify(exc instanceof Error ? exc.message : String(exc), "error");
    }
  }

  async function handleCancelScan(): Promise<void> {
    if (!activeScan || cancelling) return;
    setCancelling(true);
    setScanPhase("Stopping scan");
    try {
      await apiPost(`/api/scans/${encodeURIComponent(activeScan.id)}/cancel`, {});
      notify("Stop requested — the scan ends after the request in flight.", "info");
    } catch (exc) {
      setCancelling(false);
      notify(exc instanceof Error ? exc.message : String(exc), "error");
    }
  }

  async function persistFindingState(finding: Finding, patch: Partial<FindingMutationState> & { note?: string }) {
    if (!activeScan) {
      notify("Run a backend scan first, then update findings from the refreshed scan results.", "info");
      return;
    }
    try {
      await apiPatch(`/api/scans/${encodeURIComponent(activeScan.id)}/findings/${encodeURIComponent(finding.id)}`, patch);
      await refreshScanFindings(activeScan.id, activeScan, finding.id);
      await refreshFindingHistory(activeScan.id, finding.id);
      notify(`Finding ${finding.id} updated and persisted`);
    } catch (exc) {
      notify(exc instanceof Error ? exc.message : String(exc), "error");
    }
  }

  const handleMarkForReview = (finding: Finding) => persistFindingState(finding, { status: "triaged", remediation_note: "Marked for reviewer validation from the WebUI mitigation panel.", note: "Marked for review from WebUI." });
  const handleSelectFinding = (id: string) => { setSelectedFindingId(id); setView("workspace"); };

  // Deploy-to-scan hand-off from the Projects tab: switch to Overview and kick
  // off a baseline scan against the freshly created Agent Lab target.
  // handleToggleScan owns the scanTargetId sync for the explicit-target path.
  const runScanForTarget = (targetId: string) => {
    if (scanning) {
      notify("A scan is already running — wait for it to finish before starting another.", "info");
      return;
    }
    setView("overview");
    void handleToggleScan(targetId);
  };

  const navPane = <AssetNavigationPane assets={displayAssets} findingsById={findingsById} selectedFindingId={selectedFindingId} onSelectFinding={handleSelectFinding} />;
  const middlePane = selectedFinding ? <AnalysisWorkspace finding={selectedFinding} asset={selectedAsset} scanId={activeScan?.id} history={selectedFindingHistory} onMarkForReview={() => handleMarkForReview(selectedFinding)} onChangeStatus={(patch) => void persistFindingState(selectedFinding, patch)} /> : <EmptyState icon={MousePointerSquareDashed} title="No scan finding selected" description="Run a scan, or open a saved result." />;
  const intelPane = selectedFinding ? <IntelligencePanel finding={selectedFinding} /> : <EmptyState icon={ScanSearch} title="No finding selected" description="Select a finding to see intelligence and the assistant." />;

  return (
    <AppShell view={view} onChangeView={setView} theme={theme} onToggleTheme={toggleTheme} scanning={scanning} scanStatusLabel={scanPhase} scanProgressPercent={scanProgressPercent} scanFindingCount={liveFindingCount} scanDisabled={configuredTargetIds.length === 0} onToggleScan={() => void handleToggleScan()} onCancelScan={() => void handleCancelScan()} cancelling={cancelling} targets={configuredTargets} selectedTarget={scanTargetId} onSelectTarget={setScanTargetId}>
      {view === "projects" ? <ProjectImporter onTargetsChanged={() => void loadTargets()} onRunScan={runScanForTarget} onNavigate={setView} /> : view === "agents" ? <AgentHost onTargetsChanged={() => void loadTargets()} /> : view === "targets" ? <TargetsManager onTargetsChanged={() => void loadTargets()} /> : view === "overview" ? (
        <div className="h-full overflow-y-auto scrollbar-thin p-4 sm:p-6">
          <div className="mx-auto max-w-[1400px]">
            <DashboardOverview metrics={metrics} trend={trend} distribution={runtimeFindings.length ? distribution : emptySeverityDistribution} loading={dashboardLoading} hasScans={Boolean(activeScan)} />
            {!dashboardLoading && !activeScan ? <section className="mt-4 rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground shadow-card"><h2 className="text-lg font-extrabold text-foreground">No scans yet</h2><p className="mt-1 max-w-2xl">Configure an authorised target, then run a scan.</p><div className="ui-action-row mt-4"><button type="button" onClick={() => setView("targets")} className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-bold text-primary-foreground shadow-card transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><Server className="size-4" />Configure a target</button>{configuredTargetIds.length > 0 ? <button type="button" onClick={() => void handleToggleScan()} disabled={scanning} className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-canvas px-3 py-2 text-xs font-bold text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><Play className="size-4" />Run a scan</button> : null}</div></section> : null}
            {/* A run that was cancelled or timed out produced no findings because
                it did not finish — saying it "completed without findings" would
                read as a clean result. */}
            {activeScan && !runtimeFindings.length && !dashboardLoading ? (
              scanStateStyle(activeScan.status).successful ? (
                <section className="mt-4 rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground shadow-card"><h2 className="text-lg font-extrabold text-foreground">No findings returned</h2><p className="mt-1 max-w-2xl">The scan completed without findings. Reports remain in the output directory.</p></section>
              ) : (
                <section className="mt-4 rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground shadow-card"><h2 className="text-lg font-extrabold text-foreground">Scan {scanStateStyle(activeScan.status).label.toLowerCase()}</h2><p className="mt-1 max-w-2xl">{activeScan.error || "The run ended before it produced results."}</p></section>
              )
            ) : null}
            {liveScanEvents.length ? <section className="mt-4 rounded-xl border border-border bg-card p-4 shadow-card" aria-live="polite"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Live backend scan</p><h2 className="mt-1 text-lg font-extrabold">{scanPhase}</h2></div><p className="text-sm font-semibold text-muted-foreground">{Math.round(scanProgressPercent)}% · {liveFindingCount} findings</p></div><div className="mt-3 h-2 overflow-hidden rounded bg-muted"><div className="h-full bg-[var(--accent-sage)]" style={{ width: `${scanProgressPercent}%` }} /></div><ol className="mt-3 max-h-48 space-y-1 overflow-auto text-xs text-muted-foreground">{liveScanEvents.slice(-10).map((event, index) => <li key={`${event.event_id}-${index}`}>{event.message}</li>)}</ol></section> : null}
          </div>
        </div>
      ) : <WorkspaceLayout left={navPane} middle={middlePane} right={intelPane} />}
    </AppShell>
  );
}

export default function App() {
  return <TooltipProvider delayDuration={200}><ToastProvider><ConsoleInner /></ToastProvider></TooltipProvider>;
}
