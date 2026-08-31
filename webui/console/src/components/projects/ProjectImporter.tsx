import { useCallback, useEffect, useRef, useState } from "react";
import {
  FolderUp,
  GitBranch,
  Loader2,
  RefreshCw,
  Trash2,
  FileCode2,
  HardDrive,
  Rocket,
  ShieldAlert,
  CheckCircle2,
  Activity,
  ScanSearch,
  Server,
  ChevronDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiGet, apiPost } from "@/lib/api";

/**
 * Projects — import an AI agent codebase, then deploy it as a working, scannable
 * VulnoraIQ target without leaving the console.
 *
 * Replaces the old `<iframe src="/agent-lab">`, which the app's own
 * `frame-ancestors 'none'` / `X-Frame-Options: DENY` headers always blocked (the
 * page rendered blank). This panel talks to the same `/api/agent-lab` endpoints
 * directly, so no self-framing is needed, and it carries the full
 * import → analyse → deploy → auto-target → scan flow so there is no dead end
 * after import.
 */

interface AgentProject {
  id: string;
  source?: string;
  path?: string;
  file_count?: number;
  size_bytes?: number;
  framework?: string;
  has_dockerfile?: boolean;
  writable?: boolean;
}

interface EndpointContract {
  method?: string;
  path?: string;
  param_style?: string;
  param_key?: string;
  response_shape?: string;
  response_path?: string;
}

interface ProjectAnalysis {
  id: string;
  framework?: string;
  ports?: number[];
  endpoints?: EndpointContract[];
  /** Authoritative inference endpoint chosen by the backend ranking. */
  selected_endpoint?: EndpointContract | null;
  has_dockerfile?: boolean;
  env_vars?: { name: string; required?: boolean; secret?: boolean }[];
  file_count?: number;
}

interface ProviderPreset {
  display_name?: string;
  requires_api_key?: boolean;
  default_base_url?: string;
  default_model?: string;
}

interface DeploymentResult {
  deployed?: boolean;
  project_id?: string;
  deployment_mode?: string;
  status?: string;
  base_url?: string;
  health_status?: string;
  container_port?: number | null;
  host_port?: number | null;
  target_ids?: string[];
  endpoint_contract?: EndpointContract;
}

interface AgentLabState {
  projects: AgentProject[];
  run_mode?: string;
  provider_presets?: Record<string, ProviderPreset>;
}

type DeployMode = "container" | "external" | "hybrid";
type TargetType = "http_json" | "chat_completions";

interface ProjectImporterProps {
  /** Reload the app-level target list after a deploy creates one. */
  onTargetsChanged?: () => void;
  /** Run a baseline scan against a freshly-created target and switch to Overview. */
  onRunScan?: (targetId: string) => void;
  /** Switch the console to another tab (e.g. Targets). */
  onNavigate?: (view: "overview" | "workspace" | "targets" | "agents" | "projects") => void;
}

function formatBytes(bytes?: number): string {
  if (!bytes || bytes <= 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 && unit > 0 ? 1 : 0)} ${units[unit]}`;
}

function sanitiseId(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

/**
 * The inference endpoint to preview. Prefer the backend's authoritative
 * `selected_endpoint` (same ranking the deploy path uses) and fall back to the
 * first endpoint only if an older backend did not provide it — so the preview
 * never disagrees with what actually gets registered.
 */
function previewEndpoint(analysis: ProjectAnalysis | null): EndpointContract | null {
  if (!analysis) return null;
  if (analysis.selected_endpoint) return analysis.selected_endpoint;
  return analysis.endpoints?.[0] || null;
}

export function ProjectImporter({ onTargetsChanged, onRunScan, onNavigate }: ProjectImporterProps) {
  const [projects, setProjects] = useState<AgentProject[]>([]);
  const [runMode, setRunMode] = useState<string>("");
  const [providerPresets, setProviderPresets] = useState<Record<string, ProviderPreset>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [notice, setNotice] = useState<string>("");
  const [gitUrl, setGitUrl] = useState("");
  const [gitBranch, setGitBranch] = useState("");
  const folderInputRef = useRef<HTMLInputElement>(null);

  // Per-project deploy panel state.
  const [selectedId, setSelectedId] = useState<string>("");
  const [analysis, setAnalysis] = useState<ProjectAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [deployMode, setDeployMode] = useState<DeployMode>("container");
  const [targetType, setTargetType] = useState<TargetType>("http_json");
  const [externalBaseUrl, setExternalBaseUrl] = useState("");
  const [providerKind, setProviderKind] = useState("");
  const [providerBaseUrl, setProviderBaseUrl] = useState("");
  const [providerModel, setProviderModel] = useState("");
  const [providerApiKey, setProviderApiKey] = useState("");
  const [authAck, setAuthAck] = useState(false);
  const [deployment, setDeployment] = useState<DeploymentResult | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiGet<AgentLabState>("/api/agent-lab");
      setProjects(data.projects || []);
      setRunMode(data.run_mode || "");
      setProviderPresets(data.provider_presets || {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selectProject = useCallback(async (id: string) => {
    setSelectedId(id);
    setDeployment(null);
    setError("");
    setNotice("");
    setAnalysis(null);
    // Reset the deploy form so nothing (deploy mode, external URL, provider, or
    // the authorization acknowledgement) leaks from the previously selected
    // project into this one.
    setDeployMode("container");
    setTargetType("http_json");
    setExternalBaseUrl("");
    setProviderKind("");
    setProviderBaseUrl("");
    setProviderModel("");
    setProviderApiKey("");
    setAuthAck(false);
    setAnalyzing(true);
    try {
      const data = await apiGet<ProjectAnalysis>(`/api/agent-lab/projects/${encodeURIComponent(id)}/analyze`);
      setAnalysis(data);
      // Container mode needs a Dockerfile or a generatable framework; if neither,
      // nudge toward External mode so the flow never dead-ends.
      if (!data.has_dockerfile && !data.framework) setDeployMode("external");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setAnalyzing(false);
    }
  }, []);

  const importFolder = useCallback(async (files: FileList) => {
    if (!files.length) return;
    setError("");
    setNotice("");
    setBusy("folder");
    try {
      const first = files[0] as File & { webkitRelativePath?: string };
      const topDir = (first.webkitRelativePath || first.name).split("/")[0];
      const projectId = sanitiseId(topDir) || `agent-${Date.now()}`;

      const { default: JSZip } = await import("jszip");
      const zip = new JSZip();
      let total = 0;
      for (const file of Array.from(files)) {
        const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
        const inner = rel.split("/").slice(1).join("/") || file.name;
        if (/(^|\/)(\.git|node_modules|__pycache__|\.venv)(\/|$)/.test(rel)) continue;
        total += file.size;
        if (total > 48 * 1024 * 1024) throw new Error("Folder exceeds the 48 MB import limit. Remove build artifacts and retry.");
        zip.file(inner, file);
      }
      const base64 = await zip.generateAsync({ type: "base64", compression: "DEFLATE" });
      const result = await apiPost<{ project_id: string }>("/api/agent-lab/import/archive",
        { archive_base64: base64, project_id: projectId });
      setNotice(`Imported “${result.project_id}” from folder.`);
      await refresh();
      await selectProject(result.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Folder import failed.");
    } finally {
      setBusy("");
      if (folderInputRef.current) folderInputRef.current.value = "";
    }
  }, [refresh, selectProject]);

  const importGit = useCallback(async () => {
    if (!gitUrl.trim()) return;
    setError("");
    setNotice("");
    setBusy("git");
    try {
      const result = await apiPost<{ project_id: string }>("/api/agent-lab/import/git",
        { url: gitUrl.trim(), branch: gitBranch.trim() || undefined });
      setNotice(`Cloned “${result.project_id}” from Git.`);
      setGitUrl("");
      setGitBranch("");
      await refresh();
      await selectProject(result.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Git import failed.");
    } finally {
      setBusy("");
    }
  }, [gitUrl, gitBranch, refresh, selectProject]);

  const removeProject = useCallback(async (id: string) => {
    setError("");
    setNotice("");
    setBusy(`del:${id}`);
    try {
      await apiPost(`/api/agent-lab/projects/${encodeURIComponent(id)}/delete`, {});
      setNotice(`Removed “${id}”.`);
      if (selectedId === id) { setSelectedId(""); setAnalysis(null); setDeployment(null); }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove project.");
    } finally {
      setBusy("");
    }
  }, [refresh, selectedId]);

  const onProviderKind = useCallback((kind: string) => {
    setProviderKind(kind);
    const preset = providerPresets[kind];
    if (preset) {
      setProviderBaseUrl(preset.default_base_url || "");
      setProviderModel(preset.default_model || "");
    }
  }, [providerPresets]);

  const deploy = useCallback(async () => {
    if (!selectedId) return;
    setError("");
    setNotice("");
    if (deployMode !== "container" && !authAck) {
      setError("Confirm you are authorized to test this endpoint / external model before deploying.");
      return;
    }
    if (deployMode === "external" && !externalBaseUrl.trim()) {
      setError("External endpoint mode needs a base URL (e.g. http://127.0.0.1:9000).");
      return;
    }
    if (deployMode === "hybrid" && !providerKind && !providerBaseUrl.trim()) {
      setError("Hybrid mode needs an external model provider — select one or set its base URL.");
      return;
    }
    setBusy("deploy");
    setDeployment(null);
    try {
      const firstPort = analysis?.ports?.[0] || 8000;
      const body = {
        deployment_mode: deployMode,
        authorization_acknowledged: authAck,
        base_url: externalBaseUrl.trim(),
        provider: deployMode === "hybrid" ? { kind: providerKind, base_url: providerBaseUrl, model: providerModel, api_key: providerApiKey } : {},
        env: {},
        gpu: { mode: "cpu", device_ids: "" },
        ports: [firstPort],
        publish_ports: true,
        // Let the backend derive method/endpoint/body/response from the detected
        // contract — this is the auto-target behaviour we want to showcase.
        target: { type: targetType, safety_profile: "local_lab_safe" },
      };
      const result = await apiPost<DeploymentResult>(`/api/agent-lab/projects/${encodeURIComponent(selectedId)}/deploy`,
        body);
      if (!result.deployed || !(result.target_ids || []).length) {
        throw new Error("Deploy did not register a target. Check the deployment logs and retry.");
      }
      setDeployment(result);
      setNotice(`Deployed “${result.project_id}” — created target ${(result.target_ids || []).join(", ")}.`);
      onTargetsChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deploy failed.");
    } finally {
      setBusy("");
    }
  }, [selectedId, deployMode, authAck, externalBaseUrl, analysis, providerKind, providerBaseUrl, providerModel, providerApiKey, targetType, onTargetsChanged]);

  // For chat_completions the backend ignores the detected route and always
  // registers POST /v1/chat/completions, so preview that instead of the raw
  // HTTP route to avoid misrepresenting what gets scanned.
  const contract: EndpointContract | null =
    targetType === "chat_completions"
      ? { method: "POST", path: "/v1/chat/completions", param_style: "json", param_key: "messages", response_shape: "json" }
      : previewEndpoint(analysis);
  const selectedPreset = providerPresets[providerKind];

  return (
    <section className="h-full overflow-y-auto p-4 scrollbar-thin sm:p-6">
      <div className="mx-auto max-w-5xl space-y-5">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Agent Lab</p>
            <h2 className="text-xl font-extrabold">Projects</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Import an AI agent codebase, then deploy it as a working scan target — no manual Docker or target edits.
              {runMode ? <span className="ml-1 text-xs">Run mode: <span className="font-semibold">{runMode}</span>.</span> : null}
            </p>
          </div>
          <Button size="sm" variant="ghost" onClick={() => void refresh()} disabled={loading}>
            <RefreshCw className={loading ? "size-4 animate-spin" : "size-4"} />
            <span>Refresh</span>
          </Button>
        </header>

        <div className="flex items-start gap-2 rounded-lg border border-severity-medium/40 bg-severity-medium/10 px-3 py-2 text-xs text-foreground">
          <ShieldAlert className="mt-0.5 size-4 shrink-0 text-severity-medium" />
          <p><span className="font-bold">Authorized testing only.</span> Only import, deploy, and scan agents, models, or endpoints you own or are explicitly authorized to test.</p>
        </div>

        {error ? (
          <div className="rounded-lg border border-severity-high/40 bg-severity-high/10 px-3 py-2 text-sm text-severity-high">{error}</div>
        ) : null}
        {notice ? (
          <div className="rounded-lg border border-border bg-canvas px-3 py-2 text-sm text-muted-foreground">{notice}</div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2">
          {/* Import from a local folder — the primary path. */}
          <div className="rounded-xl border border-border bg-card p-4 shadow-card">
            <div className="mb-2 flex items-center gap-2">
              <FolderUp className="size-4 text-primary" />
              <h3 className="text-sm font-bold">Import from folder</h3>
            </div>
            <p className="mb-3 text-xs text-muted-foreground">
              Pick a folder containing your agent. It is packaged in your browser and uploaded — nothing leaves until you choose it.
            </p>
            <input
              ref={folderInputRef}
              type="file"
              // @ts-expect-error non-standard but widely supported folder-select attributes
              webkitdirectory=""
              directory=""
              multiple
              className="hidden"
              onChange={(e) => e.target.files && void importFolder(e.target.files)}
            />
            <Button
              variant="primary"
              size="sm"
              disabled={busy === "folder"}
              onClick={() => folderInputRef.current?.click()}
            >
              {busy === "folder" ? <Loader2 className="size-4 animate-spin" /> : <FolderUp className="size-4" />}
              <span>{busy === "folder" ? "Packaging…" : "Choose folder"}</span>
            </Button>
          </div>

          {/* Import from a Git repository. */}
          <div className="rounded-xl border border-border bg-card p-4 shadow-card">
            <div className="mb-2 flex items-center gap-2">
              <GitBranch className="size-4 text-primary" />
              <h3 className="text-sm font-bold">Import from Git</h3>
            </div>
            <div className="space-y-2">
              <input
                className="input text-sm font-mono"
                placeholder="https://github.com/org/agent.git"
                value={gitUrl}
                onChange={(e) => setGitUrl(e.target.value)}
              />
              <input
                className="input text-sm"
                placeholder="Branch (optional)"
                value={gitBranch}
                onChange={(e) => setGitBranch(e.target.value)}
              />
              <Button variant="outline" size="sm" disabled={busy === "git" || !gitUrl.trim()} onClick={() => void importGit()}>
                {busy === "git" ? <Loader2 className="size-4 animate-spin" /> : <GitBranch className="size-4" />}
                <span>{busy === "git" ? "Cloning…" : "Clone repository"}</span>
              </Button>
            </div>
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-bold">Imported projects</h3>
            <span className="text-xs text-muted-foreground">{projects.length} total</span>
          </div>

          {loading ? (
            <p className="text-sm text-muted-foreground">Loading projects…</p>
          ) : projects.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-canvas p-8 text-center">
              <FolderUp className="mx-auto mb-2 size-6 text-muted-foreground" />
              <p className="text-sm font-semibold">No projects yet</p>
              <p className="mx-auto mt-1 max-w-sm text-xs text-muted-foreground">
                Import a folder or clone a Git repository above to start analysing an agent.
              </p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {projects.map((project) => {
                const active = project.id === selectedId;
                return (
                  <div
                    key={project.id}
                    className={`flex flex-col gap-2 rounded-xl border bg-card p-4 shadow-card transition-colors ${active ? "border-primary ring-1 ring-primary" : "border-border"}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <button type="button" className="min-w-0 flex-1 text-left" onClick={() => { if (!active) void selectProject(project.id); }}>
                        <p className="break-anywhere font-semibold">{project.id}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {project.source || "managed"}{project.framework ? ` · ${project.framework}` : ""}{project.has_dockerfile ? " · Dockerfile" : ""}
                        </p>
                      </button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={busy === `del:${project.id}` || project.writable === false}
                        onClick={() => void removeProject(project.id)}
                        title={project.writable === false ? "Read-only project" : "Remove project"}
                      >
                        {busy === `del:${project.id}` ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
                      </Button>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1"><FileCode2 className="size-3.5" />{project.file_count ?? "—"} files</span>
                      <span className="inline-flex items-center gap-1"><HardDrive className="size-3.5" />{formatBytes(project.size_bytes)}</span>
                    </div>
                    <Button
                      variant={active ? "primary" : "outline"}
                      size="sm"
                      className="mt-1 self-start"
                      disabled={active}
                      onClick={() => { if (!active) void selectProject(project.id); }}
                    >
                      <Rocket className="size-4" />
                      <span>{active ? "Selected" : "Analyse & deploy"}</span>
                      {!active ? <ChevronDown className="size-3.5" /> : null}
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Deploy panel for the selected project. */}
        {selectedId ? (
          <div className="rounded-xl border border-border bg-card p-4 shadow-card">
            <div className="mb-3 flex items-center gap-2">
              <Rocket className="size-4 text-primary" />
              <h3 className="text-sm font-bold">Deploy “{selectedId}” as a scan target</h3>
              {analyzing ? <Loader2 className="size-4 animate-spin text-muted-foreground" /> : null}
            </div>

            {/* Detected contract summary. */}
            {analysis ? (
              <div className="mb-4 grid gap-2 rounded-lg border border-border bg-canvas p-3 text-xs sm:grid-cols-2">
                <div><span className="text-muted-foreground">Framework:</span> <span className="font-semibold">{analysis.framework || "unknown"}</span></div>
                <div><span className="text-muted-foreground">Ports:</span> <span className="font-semibold">{(analysis.ports || []).join(", ") || "—"}</span></div>
                <div className="sm:col-span-2">
                  <span className="text-muted-foreground">{targetType === "chat_completions" ? "Target contract:" : "Detected inference endpoint:"}</span>{" "}
                  {contract ? (
                    <span className="font-mono font-semibold">{contract.method} {contract.path} · {contract.param_style === "query" ? `?${contract.param_key}=` : `{${contract.param_key}}`} → {contract.response_shape}</span>
                  ) : (
                    <span className="font-semibold">none detected (you can supply an external endpoint)</span>
                  )}
                </div>
                <div className="sm:col-span-2 text-muted-foreground">
                  The auto-created target uses this contract — correct method, endpoint, request body, and response extraction — with no manual edits.
                </div>
              </div>
            ) : null}

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-semibold text-muted-foreground">
                Deployment mode
                <select className="input mt-1 text-sm" value={deployMode} onChange={(e) => setDeployMode(e.target.value as DeployMode)}>
                  <option value="container">Containerized local agent</option>
                  <option value="hybrid">Hybrid (local app + external model)</option>
                  <option value="external">External endpoint (no build)</option>
                </select>
              </label>
              <label className="text-xs font-semibold text-muted-foreground">
                Target type
                <select className="input mt-1 text-sm" value={targetType} onChange={(e) => setTargetType(e.target.value as TargetType)}>
                  <option value="http_json">HTTP JSON / text</option>
                  <option value="chat_completions">OpenAI Chat Completions</option>
                </select>
              </label>

              {deployMode === "external" ? (
                <label className="text-xs font-semibold text-muted-foreground sm:col-span-2">
                  External base URL
                  <input className="input mt-1 text-sm font-mono" placeholder="http://127.0.0.1:9000" value={externalBaseUrl} onChange={(e) => setExternalBaseUrl(e.target.value)} />
                </label>
              ) : null}

              {deployMode === "hybrid" ? (
                <>
                  <label className="text-xs font-semibold text-muted-foreground">
                    Model provider
                    <select className="input mt-1 text-sm" value={providerKind} onChange={(e) => onProviderKind(e.target.value)}>
                      <option value="">Select provider…</option>
                      {Object.entries(providerPresets).map(([k, v]) => (
                        <option key={k} value={k}>{v.display_name || k}</option>
                      ))}
                    </select>
                  </label>
                  <label className="text-xs font-semibold text-muted-foreground">
                    Model provider base URL
                    <input className="input mt-1 text-sm font-mono" placeholder="http://host.docker.internal:11434/v1" value={providerBaseUrl} onChange={(e) => setProviderBaseUrl(e.target.value)} />
                  </label>
                  <label className="text-xs font-semibold text-muted-foreground sm:col-span-2">
                    Model
                    <input className="input mt-1 text-sm" placeholder="llama3.1, qwen2.5, …" value={providerModel} onChange={(e) => setProviderModel(e.target.value)} />
                  </label>
                  {selectedPreset?.requires_api_key ? (
                    <label className="text-xs font-semibold text-muted-foreground sm:col-span-2">
                      API key <span className="font-normal">(not persisted; injected into the container runtime)</span>
                      <input type="password" autoComplete="off" className="input mt-1 text-sm" placeholder="sk-…" value={providerApiKey} onChange={(e) => setProviderApiKey(e.target.value)} />
                    </label>
                  ) : null}
                </>
              ) : null}
            </div>

            {deployMode !== "container" ? (
              <label className="mt-3 flex items-start gap-2 text-xs text-muted-foreground">
                <input type="checkbox" className="mt-0.5" checked={authAck} onChange={(e) => setAuthAck(e.target.checked)} />
                <span>I am authorized to test the supplied endpoint / external model, and any configured credentials are approved for security testing.</span>
              </label>
            ) : null}

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Button variant="primary" size="sm" onClick={() => void deploy()} disabled={busy === "deploy" || analyzing}>
                {busy === "deploy" ? <Loader2 className="size-4 animate-spin" /> : <Rocket className="size-4" />}
                <span>{busy === "deploy" ? "Deploying…" : "Build / Run / Auto-create target"}</span>
              </Button>
              {deployMode === "container" ? (
                <span className="text-xs text-muted-foreground">Builds and runs the container on a free host port, health-checks it, and registers a target.</span>
              ) : null}
            </div>

            {/* Deployment summary. */}
            {deployment?.deployed ? (
              <div className="mt-4 rounded-lg border border-severity-low/40 bg-severity-low/10 p-3">
                <div className="mb-2 flex items-center gap-2 text-sm font-bold text-severity-low">
                  <CheckCircle2 className="size-4" />
                  <span>Deployment ready</span>
                </div>
                <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
                  <Row label="Mode" value={deployment.deployment_mode} />
                  <Row label="Reachable base URL" value={deployment.base_url} mono />
                  <Row label="Selected endpoint" value={`${deployment.endpoint_contract?.method || ""} ${deployment.endpoint_contract?.path || ""}`.trim()} mono />
                  <Row label="Target ID" value={(deployment.target_ids || []).join(", ")} mono />
                  <Row label="Container port" value={deployment.container_port != null ? String(deployment.container_port) : "—"} />
                  <Row label="Host port" value={deployment.host_port != null ? String(deployment.host_port) : "—"} />
                  <div className="flex items-center gap-1.5">
                    <dt className="text-muted-foreground">Health:</dt>
                    <dd className="inline-flex items-center gap-1 font-semibold"><Activity className="size-3.5" />{deployment.health_status || "unknown"}</dd>
                  </div>
                </dl>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button variant="primary" size="sm" onClick={() => { const id = deployment.target_ids?.[0]; if (id) onRunScan?.(id); }} disabled={!deployment.target_ids?.length}>
                    <ScanSearch className="size-4" />
                    <span>Run baseline scan</span>
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => onNavigate?.("targets")}>
                    <Server className="size-4" />
                    <span>Open in Targets</span>
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function Row({ label, value, mono }: { label: string; value?: string; mono?: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <dt className="text-muted-foreground">{label}:</dt>
      <dd className={`break-anywhere font-semibold ${mono ? "font-mono" : ""}`}>{value || "—"}</dd>
    </div>
  );
}
