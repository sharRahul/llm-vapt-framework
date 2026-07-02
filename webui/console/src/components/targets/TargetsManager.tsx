import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Filter,
  Loader2,
  PlayCircle,
  Plus,
  RefreshCw,
  Save,
  Search,
  Server,
  ShieldCheck,
  Trash2,
  Wifi,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ConnectivityResult, ScanEvent, ScanJob, TargetConfig, TargetRecord } from "@/types";
import { cn } from "@/lib/utils";

const ENVIRONMENTS = ["local", "lab", "internal", "production-like"];
const SCAN_PROFILES = ["baseline", "rag", "agent", "full", "owasp-aitg-full"];
const TARGET_TYPES = ["http_json", "chat_completions", "ollama_generate", "webhook_json", "rag_query", "agent_tool_loop"];

const defaultTarget = (): TargetConfig => ({
  name: "New authorised AI target",
  type: "http_json",
  base_url: "http://127.0.0.1:9090",
  endpoint_path: "/agent",
  method: "POST",
  headers: { "Content-Type": "application/json" },
  request_body_template: { prompt: "{{prompt}}" },
  response_extraction_path: "response",
  timeout: 10,
  retry: { attempts: 2, backoff_seconds: 0.2 },
  rate_limit: { requests_per_second: 1 },
  authorisation_required: true,
  safety_profile: "local_lab_safe",
  tags: ["local", "authorised"],
  owner: { name: "", contact: "" },
  environment: "local",
  allow_external: false,
});

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

async function csrfToken(): Promise<string> {
  const data = await api<{ csrf_token: string }>("/api/csrf-token");
  return data.csrf_token;
}

function parseJsonField(value: string, fallback: unknown): unknown {
  if (!value.trim()) return fallback;
  return JSON.parse(value);
}

function targetHealth(target: TargetRecord): "ready" | "needs-owner" | "needs-auth" | "external" {
  if (target.config.allow_external) return "external";
  if (target.config.authorisation_required === false) return "needs-auth";
  return "ready";
}

function endpointLabel(target: TargetConfig): string {
  return target.base_url || target.endpoint || "No endpoint configured";
}

export function TargetsManager() {
  const [targets, setTargets] = useState<TargetRecord[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [draftId, setDraftId] = useState("");
  const [draft, setDraft] = useState<TargetConfig>(defaultTarget());
  const [headersText, setHeadersText] = useState("{}");
  const [bodyText, setBodyText] = useState(JSON.stringify(defaultTarget().request_body_template, null, 2));
  const [connectivity, setConnectivity] = useState<ConnectivityResult | null>(null);
  const [jobs, setJobs] = useState<ScanJob[]>([]);
  const [scanProfile, setScanProfile] = useState("baseline");
  const [query, setQuery] = useState("");
  const [environmentFilter, setEnvironmentFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveEvents, setLiveEvents] = useState<ScanEvent[]>([]);
  const [streamState, setStreamState] = useState<"idle" | "connecting" | "live" | "error" | "complete">("idle");
  // Maps a hosted-agent id to its live host base URL (http://127.0.0.1:<published port>),
  // so an agent-backed target's Base URL is always taken from Docker, never typed.
  const [agentBaseUrls, setAgentBaseUrls] = useState<Record<string, string>>({});

  const selected = useMemo(() => targets.find((target) => target.id === selectedId), [selectedId, targets]);
  const filteredTargets = useMemo(() => {
    const q = query.trim().toLowerCase();
    return targets.filter((target) => {
      const envMatch = environmentFilter === "all" || (target.config.environment || "local") === environmentFilter;
      const searchText = [
        target.id,
        target.config.name,
        target.config.type,
        target.config.base_url,
        target.config.endpoint,
        target.config.owner?.contact,
        ...(target.config.tags || []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return envMatch && (!q || searchText.includes(q));
    });
  }, [environmentFilter, query, targets]);
  const latestJobs = useMemo(() => jobs.filter((job) => job.target === draftId).slice(0, 5), [draftId, jobs]);
  const readyCount = useMemo(() => targets.filter((target) => targetHealth(target) === "ready").length, [targets]);

  async function loadTargets() {
    setLoading(true);
    setError(null);
    try {
      const data = await api<{ targets: Record<string, TargetConfig> }>("/api/targets");
      const records = Object.entries(data.targets || {}).map(([id, config]) => ({ id, config }));
      setTargets(records);
      const next = records.find((record) => record.id === selectedId) || records[0];
      if (next) selectTarget(next);
      else { setSelectedId(""); setDraftId("");
        setDraft(defaultTarget());
        setHeadersText("{}");
        setBodyText("{}");
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setLoading(false);
    }
  }

  async function loadAgentBaseUrls() {
    try {
      const data = await api<{ agents: { id: string; ports?: string }[] }>("/api/agents");
      const map: Record<string, string> = {};
      for (const agent of data.agents || []) {
        // ports look like "0.0.0.0:8099->8099/tcp, [::]:8099->8099/tcp"; take the first host port.
        const match = /:(\d+)->/.exec(agent.ports || "");
        if (match) map[agent.id] = `http://127.0.0.1:${match[1]}`;
      }
      setAgentBaseUrls(map);
    } catch {
      // Agent host unavailable; fall back to the stored base URL.
    }
  }

  async function loadJobs() {
    try {
      const data = await api<{ jobs: ScanJob[] }>("/api/scans");
      setJobs(data.jobs || []);
    } catch {
      // Older or unauthenticated deployments can still manage targets without scan history.
    }
  }

  function selectTarget(record: TargetRecord) {
    setSelectedId(record.id);
    setDraftId(record.id);
    setDraft({ ...defaultTarget(), ...record.config });
    setHeadersText(JSON.stringify(record.config.headers || {}, null, 2));
    setBodyText(JSON.stringify(record.config.request_body_template || defaultTarget().request_body_template, null, 2));
    setConnectivity(null);
  }

  function newTarget() {
    const next = defaultTarget();
    setSelectedId("");
    setDraftId("new_authorised_target");
    setDraft(next);
    setHeadersText(JSON.stringify(next.headers, null, 2));
    setBodyText(JSON.stringify(next.request_body_template, null, 2));
    setConnectivity(null);
  }

  function buildTarget(): TargetConfig {
    return {
      ...draft,
      headers: parseJsonField(headersText, {}) as Record<string, string>,
      request_body_template: parseJsonField(bodyText, { prompt: "{{prompt}}" }),
      tags: typeof draft.tags === "string" ? String(draft.tags).split(",").map((tag) => tag.trim()).filter(Boolean) : draft.tags,
    };
  }

  async function saveTarget() {
    setSaving(true);
    setError(null);
    try {
      const token = await csrfToken();
      const target = buildTarget();
      await api("/api/targets/save", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
        body: JSON.stringify({ id: draftId, target }),
      });
      await loadTargets();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSaving(false);
    }
  }

  async function deleteTarget() {
    if (!window.confirm(`Delete runtime target '${draftId}'? Built-in targets are not removed.`)) return;
    setSaving(true);
    setError(null);
    try {
      const token = await csrfToken();
      await api("/api/targets/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
        body: JSON.stringify({ id: draftId }),
      });
      await loadTargets();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSaving(false);
    }
  }

  async function testConnectivity() {
    setTesting(true);
    setError(null);
    setConnectivity(null);
    try {
      if (!targets.some((target) => target.id === draftId)) await saveTarget();
      const token = await csrfToken();
      const data = await api<ConnectivityResult>(`/api/targets/${encodeURIComponent(draftId)}/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
        body: JSON.stringify({}),
      });
      setConnectivity(data);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setTesting(false);
    }
  }

  function connectScanEvents(jobId: string) {
    setLiveEvents([]);
    setStreamState("connecting");
    const source = new EventSource(`/api/scans/${encodeURIComponent(jobId)}/events`, { withCredentials: true });
    const onEvent = (event: MessageEvent) => {
      const payload = JSON.parse(event.data) as ScanEvent;
      setLiveEvents((prev) => [...prev.slice(-49), payload]);
      setStreamState("live");
      if (["scan_completed", "scan_failed"].includes(payload.type)) {
        setScanning(false);
        setStreamState(payload.type === "scan_completed" ? "complete" : "error");
        source.close();
        void loadJobs();
      }
    };
    ["scan_queued", "scan_started", "target_validated", "phase_started", "check_started", "check_completed", "finding_created", "evidence_saved", "report_written", "scan_completed", "scan_failed", "heartbeat"].forEach((type) => source.addEventListener(type, onEvent));
    source.onerror = () => {
      setStreamState((state) => (state === "complete" ? state : "error"));
    };
  }

  async function startScan() {
    setScanning(true);
    setError(null);
    try {
      const token = await csrfToken();
      const job = await api<ScanJob>("/api/scans", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
        body: JSON.stringify({ target: draftId, profile: scanProfile, authorised: true }),
      });
      setJobs((prev) => [job, ...prev.filter((item) => item.id !== job.id)]);
      connectScanEvents(job.id);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setScanning(false);
      setStreamState("error");
    }
  }

  useEffect(() => {
    void loadTargets();
    void loadJobs();
    void loadAgentBaseUrls();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Base URL is always taken from Docker: derive it from the matching hosted agent's
  // live published port and keep it locked (no manual entry).
  const agentId = draftId.replace(/^agent-/, "");
  const dockerBaseUrl = agentBaseUrls[agentId] || "";
  const lockedBaseUrl = dockerBaseUrl || draft.base_url || "";
  useEffect(() => {
    if (dockerBaseUrl && draft.base_url !== dockerBaseUrl) {
      setDraft((d) => ({ ...d, base_url: dockerBaseUrl }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dockerBaseUrl]);

  const isExternal = draft.allow_external === true;
  // Targets backed by a deployed Agent Lab container get their Base URL from Docker and
  // are locked. Direct LLM/RAG/agent HTTP endpoints are authored here and stay editable.
  const dockerBacked = Boolean(dockerBaseUrl);
  const endpointEditable = !dockerBacked;
  const idEditable = !selected;
  const needsModel = ["chat_completions", "ollama_generate"].includes(draft.type);
  const safetyChecklist = [
    { label: "Authorisation gate", ok: draft.authorisation_required !== false },
    { label: dockerBacked ? "Base URL from Docker" : "Base URL configured", ok: Boolean(lockedBaseUrl) },
    { label: "Endpoint configured", ok: Boolean(draft.endpoint_path) },
    { label: "Model set", ok: !needsModel || Boolean(draft.model) },
  ];

  return (
    <div className="grid h-full grid-cols-1 overflow-hidden bg-canvas lg:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]">
      <aside className="max-h-[42vh] overflow-y-auto border-b border-border bg-card p-4 scrollbar-thin lg:max-h-none lg:border-b-0 lg:border-r">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h2 className="text-lg font-extrabold">Targets</h2>
            <p className="break-anywhere text-xs text-muted-foreground">Manage authorised AI systems and scan readiness.</p>
          </div>
          <Button size="sm" variant="primary" onClick={newTarget} className="shrink-0">
            <Plus className="size-4" />
            <span>Add</span>
          </Button>
        </div>
        <div className="mb-4 grid grid-cols-3 gap-2 text-center text-xs">
          <Metric label="Total" value={targets.length} />
          <Metric label="Ready" value={readyCount} />
          <Metric label="Jobs" value={jobs.length} />
        </div>
        <div className="mb-3 space-y-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} className="input pl-8 text-sm" placeholder="Search targets, owners, tags…" />
          </div>
          <div className="relative">
            <Filter className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <select value={environmentFilter} onChange={(e) => setEnvironmentFilter(e.target.value)} className="input pl-8 text-sm">
              <option value="all">All environments</option>
              {ENVIRONMENTS.map((env) => <option key={env}>{env}</option>)}
            </select>
          </div>
        </div>
        {loading ? <p className="text-sm text-muted-foreground">Loading targets…</p> : null}
        <div className="space-y-2">
          {filteredTargets.map((target) => <TargetListItem key={target.id} target={target} active={selectedId === target.id} onClick={() => selectTarget(target)} />)}
          {!loading && filteredTargets.length === 0 ? <p className="rounded-lg border border-border bg-canvas p-3 text-sm text-muted-foreground">No targets match the current filters.</p> : null}
        </div>
      </aside>

      <section className="overflow-y-auto p-4 scrollbar-thin sm:p-5">
        <div className="mx-auto max-w-6xl space-y-4">
          <div className="rounded-xl border border-border bg-card p-4 shadow-card">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Target management workspace</p>
                <h1 className="ui-title-row mt-1 text-2xl font-extrabold">
                  <span className="ui-icon"><Server className="size-6" /></span>
                  <span className="break-anywhere">{draft.name || draftId}</span>
                </h1>
                <p className="mt-1 max-w-3xl text-sm text-muted-foreground">Create, edit, validate, and launch authorised scans for local/internal AI targets from one operational cockpit.</p>
              </div>
              <div className="ui-action-row justify-start sm:justify-end">
                <Button variant="secondary" onClick={() => void loadJobs()} className="w-full sm:w-auto"><RefreshCw /> <span>Refresh jobs</span></Button>
                <Button variant="secondary" onClick={testConnectivity} disabled={testing} className="w-full sm:w-auto">{testing ? <Loader2 className="animate-spin" /> : <Wifi />} <span>Test connectivity</span></Button>
                <Button variant="primary" onClick={saveTarget} disabled={saving} className="w-full sm:w-auto">{saving ? <Loader2 className="animate-spin" /> : <Save />} <span>Save</span></Button>
                <Button variant="danger" onClick={deleteTarget} disabled={saving} className="w-full sm:w-auto"><Trash2 /> <span>Delete</span></Button>
              </div>
            </div>
            {selected ? null : <p className="mt-2 text-xs text-muted-foreground">Creating a new runtime target.</p>}
            {isExternal ? <Warning title="External host override enabled" body="Only enable allow_external for systems you own or are explicitly authorised to assess. The backend still requires the normal non-demo authorisation confirmation before scans." /> : null}
            {error ? <Warning title="Target error" body={error} danger /> : null}
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(300px,360px)]">
            <div className="space-y-4">
              <div className="grid gap-4 lg:grid-cols-2">
                <Field label="Target ID">
                  <input value={draftId} onChange={(e) => setDraftId(e.target.value.replace(/[^A-Za-z0-9_-]/g, "_"))} readOnly={!idEditable} tabIndex={idEditable ? 0 : -1} aria-readonly={!idEditable} className={cn("input font-mono", !idEditable && "cursor-not-allowed opacity-70")} placeholder="my_llm_endpoint" />
                  {idEditable ? <span className="mt-1 block text-[11px] text-muted-foreground">Letters, numbers, hyphens, underscores. Fixed once saved.</span> : null}
                </Field>
                <Field label="Display name"><input value={draft.name || ""} onChange={(e) => setDraft({ ...draft, name: e.target.value })} className="input" /></Field>
                <Field label="Target type">
                  <select value={draft.type} onChange={(e) => setDraft({ ...draft, type: e.target.value })} disabled={dockerBacked} className={cn("input", dockerBacked && "cursor-not-allowed opacity-70")}>
                    {TARGET_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                </Field>
                <Field label="Environment">
                  <select value={draft.environment || "local"} onChange={(e) => setDraft({ ...draft, environment: e.target.value })} className="input">
                    {ENVIRONMENTS.map((env) => <option key={env} value={env}>{env}</option>)}
                  </select>
                </Field>
                <Field label="Base URL">
                  <input value={lockedBaseUrl} onChange={(e) => setDraft({ ...draft, base_url: e.target.value })} readOnly={!endpointEditable} tabIndex={endpointEditable ? 0 : -1} aria-readonly={!endpointEditable} className={cn("input font-mono", !endpointEditable && "cursor-not-allowed opacity-70")} placeholder="http://127.0.0.1:8000" />
                  <span className="mt-1 block text-[11px] text-muted-foreground">{dockerBacked ? "From the deployed agent container." : "Loopback/private host of the AI system under test."}</span>
                </Field>
                <Field label="Endpoint path"><input value={draft.endpoint_path || ""} onChange={(e) => setDraft({ ...draft, endpoint_path: e.target.value })} readOnly={!endpointEditable} tabIndex={endpointEditable ? 0 : -1} aria-readonly={!endpointEditable} className={cn("input font-mono", !endpointEditable && "cursor-not-allowed opacity-70")} placeholder="/v1/chat/completions" /></Field>
                {needsModel ? <Field label="Model"><input value={draft.model || ""} onChange={(e) => setDraft({ ...draft, model: e.target.value })} className="input font-mono" placeholder="gpt-4o-mini / llama3" /></Field> : null}
                <Field label="Auth token env var"><input value={draft.auth_token_env || draft.token_env_var || ""} onChange={(e) => setDraft({ ...draft, auth_token_env: e.target.value, token_env_var: undefined })} className="input font-mono" placeholder="LLM_VAPT_TARGET_TOKEN" /></Field>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <Field label="Response extraction path"><input value={draft.response_extraction_path || ""} onChange={(e) => setDraft({ ...draft, response_extraction_path: e.target.value })} readOnly={!endpointEditable} tabIndex={endpointEditable ? 0 : -1} aria-readonly={!endpointEditable} className={cn("input font-mono", !endpointEditable && "cursor-not-allowed opacity-70")} placeholder="choices.0.message.content" /></Field>
                <Field label="Request body template JSON"><textarea value={bodyText} onChange={(e) => setBodyText(e.target.value)} readOnly={!endpointEditable} tabIndex={endpointEditable ? 0 : -1} aria-readonly={!endpointEditable} className={cn("input min-h-32 font-mono text-xs", !endpointEditable && "cursor-not-allowed opacity-70")} placeholder={'{ "prompt": "{{prompt}}" }'} /></Field>
              </div>
              <div className="grid gap-4">
                <Toggle checked={draft.authorisation_required !== false} onChange={(checked) => setDraft({ ...draft, authorisation_required: checked })} title="Authorisation required" body="Required for all real targets." />
              </div>
              <p className="text-[11px] text-muted-foreground">{dockerBacked ? "Endpoint, base URL, and response path come from the deployed agent container (Agents tab) and are locked here." : "Configure a direct LLM, RAG, or agent HTTP endpoint here. Leave the request body as {{prompt}} to use the built-in template for the selected type. Use empty {} to send the type default."}</p>
            </div>

            <aside className="space-y-4">
              <Panel title="Readiness guardrails" icon={<ShieldCheck className="size-4" />}>
                <div className="space-y-2">{safetyChecklist.map((item) => <ChecklistItem key={item.label} {...item} />)}</div>
              </Panel>
              <Panel title="Launch scan" icon={<PlayCircle className="size-4" />}>
                <select value={scanProfile} onChange={(e) => setScanProfile(e.target.value)} className="input text-sm">{SCAN_PROFILES.map((profile) => <option key={profile}>{profile}</option>)}</select>
                <Button className="mt-3 w-full" variant="success" onClick={startScan} disabled={scanning || draft.authorisation_required === false}>{scanning ? <Loader2 className="animate-spin" /> : <PlayCircle />} <span>Start authorised scan</span></Button>
                <p className="mt-2 text-xs text-muted-foreground">Live progress streams from the authenticated SSE endpoint. State: {streamState}.</p>
                {liveEvents.length ? <div className="mt-3 space-y-2" aria-live="polite">
                  <div className="h-2 overflow-hidden rounded bg-muted"><div className="h-full bg-[var(--accent-sage)]" style={{ width: `${Math.max(...liveEvents.map((event) => event.progress?.percent || 0))}%` }} /></div>
                  <p className="break-anywhere text-xs font-semibold">{liveEvents[liveEvents.length - 1]?.phase || liveEvents[liveEvents.length - 1]?.type} · findings {liveEvents.filter((event) => event.type === "finding_created").length}</p>
                  <ol className="max-h-40 space-y-1 overflow-auto text-xs text-muted-foreground">{liveEvents.slice(-8).map((event, index) => <li className="break-anywhere" key={`${event.event_id}-${index}`}>{event.type}: {event.message}</li>)}</ol>
                </div> : null}
              </Panel>
              <Panel title="Recent jobs" icon={<RefreshCw className="size-4" />}>
                <div className="space-y-2">{latestJobs.length ? latestJobs.map((job) => <JobRow key={job.id} job={job} />) : <p className="text-sm text-muted-foreground">No scan jobs for this target yet.</p>}</div>
              </Panel>
              {connectivity ? <Panel title="Connectivity result" icon={connectivity.ready ? <CheckCircle2 className="size-4 text-[var(--sev-low)]" /> : <AlertTriangle className="size-4 text-[var(--sev-high)]" />}><pre className="code-wrap max-h-80 overflow-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(connectivity, null, 2)}</pre></Panel> : null}
            </aside>
          </div>
        </div>
      </section>
    </div>
  );
}

function TargetListItem({ target, active, onClick }: { target: TargetRecord; active: boolean; onClick: () => void }) {
  const health = targetHealth(target);
  return (
    <button onClick={onClick} className={cn("w-full rounded-lg border p-3 text-left transition-colors", active ? "border-primary bg-muted" : "border-border bg-canvas hover:bg-muted")}>
      <div className="flex items-start justify-between gap-2">
        <span className="break-anywhere font-semibold leading-snug">{target.config.name || target.id}</span>
        <StatusPill status={health} />
      </div>
      <p className="mt-1 break-anywhere text-xs text-muted-foreground">{target.id} · {target.config.type} · {target.config.environment || "local"}</p>
      <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground" title={endpointLabel(target.config)}>{endpointLabel(target.config)}</p>
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block rounded-xl border border-border bg-card p-3 text-sm font-semibold shadow-card"><span className="mb-1 block text-xs uppercase tracking-wide text-muted-foreground">{label}</span>{children}</label>;
}

function Toggle({ checked, onChange, title, body, icon }: { checked: boolean; onChange: (checked: boolean) => void; title: string; body: string; icon?: React.ReactNode }) {
  return (
    <button type="button" onClick={() => onChange(!checked)} className={cn("rounded-xl border p-3 text-left shadow-card", checked ? "border-primary bg-muted" : "border-border bg-card")}>
      <span className="ui-title-row font-bold"><span className="ui-icon">{icon}</span><span className="break-anywhere">{title}</span></span>
      <span className="mt-1 block text-xs text-muted-foreground">{body}</span>
      <span className={cn("mt-3 inline-flex rounded px-2 py-1 text-xs font-bold", checked ? "text-[#1b2110]" : "text-muted-foreground")} style={{ background: checked ? "var(--accent-sage)" : "var(--muted)" }}>{checked ? "Enabled" : "Disabled"}</span>
    </button>
  );
}

function Warning({ title, body, danger = false }: { title: string; body: string; danger?: boolean }) {
  return <div className={cn("mt-4 rounded-lg border p-3 text-sm", danger ? "border-[var(--sev-high)] bg-[var(--sev-high)]/10" : "border-[var(--sev-medium)] bg-[var(--sev-medium)]/10")}><p className="ui-title-row font-bold"><AlertTriangle className={cn("size-4 shrink-0", danger ? "text-[var(--sev-high)]" : "text-[var(--sev-medium)]")} /> <span>{title}</span></p><p className="mt-1 break-anywhere text-muted-foreground">{body}</p></div>;
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="rounded-lg border border-border bg-canvas p-2"><p className="text-lg font-extrabold">{value}</p><p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p></div>;
}

function Panel({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return <div className="rounded-xl border border-border bg-card p-4 shadow-card"><h3 className="mb-3 ui-title-row font-bold"><span className="ui-icon">{icon}</span><span className="break-anywhere">{title}</span></h3>{children}</div>;
}

function ChecklistItem({ label, ok }: { label: string; ok: boolean }) {
  return <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-canvas px-3 py-2 text-sm"><span className="break-anywhere">{label}</span>{ok ? <CheckCircle2 className="size-4 shrink-0 text-[var(--sev-low)]" /> : <AlertTriangle className="size-4 shrink-0 text-[var(--sev-medium)]" />}</div>;
}

function StatusPill({ status }: { status: ReturnType<typeof targetHealth> }) {
  const labels = { ready: "ready", "needs-owner": "owner", "needs-auth": "auth", external: "external" };
  return <span className={cn("shrink-0 rounded px-2 py-0.5 text-[10px] font-bold uppercase", status === "ready" ? "bg-[var(--accent-sage)] text-[#1b2110]" : "bg-muted text-muted-foreground")}>{labels[status]}</span>;
}

function JobRow({ job }: { job: ScanJob }) {
  return <div className="rounded-lg border border-border bg-canvas p-3 text-sm"><div className="flex items-start justify-between gap-2"><span className="break-anywhere font-mono text-xs">{job.id}</span><span className="shrink-0 rounded bg-muted px-2 py-0.5 text-[10px] font-bold uppercase text-muted-foreground">{job.status}</span></div><p className="mt-1 break-anywhere text-xs text-muted-foreground">{job.profile}{job.error ? ` · ${job.error}` : ""}</p></div>;
}
