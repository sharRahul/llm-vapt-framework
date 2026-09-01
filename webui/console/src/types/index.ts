// Strongly typed domain model for the VulnoraIQ SecOps console.

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export type FindingStatus =
  | "open"
  | "pending_review"
  | "auto_fix_available"
  | "triaged"
  | "in_progress"
  | "accepted_risk"
  | "false_positive"
  | "fixed"
  | "wont_fix";

export type AssetType =
  | "repository"
  | "file"
  | "container_image"
  | "ai_agent"
  | "llm_app"
  | "rag_store";

export interface Asset {
  id: string;
  name: string;
  type: AssetType;
  /** Filesystem path or image tag, depending on asset type. */
  locator: string;
  vulnerabilityCount: number;
  highestSeverity: Severity;
  /** 0–100 composite risk score. */
  riskScore: number;
  lastScanned: string; // ISO timestamp
  findingIds: string[];
  /** Backend job status. A failed scan must never read as a clean result. */
  scanStatus?: ScanJobStatus | string;
  /** Operator-facing reason a scan failed, when there is one. */
  scanError?: string | null;
}

export interface CodeBlock {
  language: string;
  filename: string;
  code: string;
  /** 1-based line numbers to highlight. */
  highlightLines?: number[];
  startLine?: number;
}

export interface Remediation {
  summary: string;
  /** Why the fix works, in plain language. */
  rationale: string;
  /** 0–100 model confidence in the remediation. */
  confidence: number;
  secureCode: CodeBlock;
}

export interface CveMetadata {
  id: string | null;
  publishedDate?: string;
  cvssScore?: number;
  cvssVector?: string;
  description?: string;
}

export interface CweMetadata {
  id: string;
  name: string;
  description: string;
}

export interface IntelligenceMapping {
  owaspLlm?: string;
  mitreAtlas?: string;
  exploitability: "theoretical" | "poc" | "functional" | "active";
  affectedComponent: string;
  recommendedPriority: Severity;
  policyStatus: "pass" | "warn" | "fail" | "manual_review";
  complianceTags: string[];
}

export interface MarkdownSection {
  title: string;
  body: string;
}

export interface Finding {
  id: string;
  assetId: string;
  title: string;
  severity: Severity;
  riskScore: number;
  status: FindingStatus;
  affectedPath: string;
  /** Short AI-generated explanation shown in the workspace header. */
  aiSummary: string;
  vulnerableCode: CodeBlock;
  remediation: Remediation;
  cve: CveMetadata;
  cwe: CweMetadata;
  intelligence: IntelligenceMapping;
  source: string;
  confidence: string;
  tool: string;
  observedAt: string;
  limitations: string;
  /** Evidence / attack scenario / impact / guidance / validation / references. */
  report: MarkdownSection[];
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  pending?: boolean;
}

export interface DashboardMetrics {
  totalScanned: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  autoRemediationRate: number; // percentage
  pendingReviews: number;
  meanTimeToRemediateHours: number;
  trend: {
    critical: number;
    high: number;
    autoRemediationRate: number;
    pendingReviews: number;
  };
}

export interface VulnerabilityTrendPoint {
  date: string; // e.g. "Jun 18"
  discovered: number;
  remediated: number;
  open: number;
}

export interface SeverityDistributionPoint {
  severity: Severity;
  count: number;
}

export type TargetEnvironment = "local" | "lab" | "internal" | "production-like";

export interface TargetConfig {
  name?: string;
  type: string;
  base_url?: string;
  endpoint?: string | null;
  endpoint_path?: string;
  method?: string;
  headers?: Record<string, string>;
  auth_token_env?: string;
  token_env_var?: string;
  auth_header?: string;
  auth_prefix?: string;
  request_body_template?: unknown;
  response_extraction_path?: string;
  tool_calls_path?: string;
  retrieval_context_path?: string;
  timeout?: number;
  retry?: { attempts?: number; backoff_seconds?: number };
  rate_limit?: { requests_per_second?: number };
  authorisation_required?: boolean;
  safety_profile?: string;
  tags?: string[];
  owner?: { name?: string; contact?: string };
  environment?: TargetEnvironment | string;
  allow_external?: boolean;
  model?: string;
}

export interface TargetRecord {
  id: string;
  config: TargetConfig;
}

export interface ConnectivityResult {
  target_id: string;
  ready: boolean;
  normalized_response?: string;
  status_code?: number;
  error?: { type?: string; message?: string } | null;
  request?: unknown;
  response_preview?: unknown;
}

export type ScanJobStatus =
  | "queued"
  | "running"
  | "analysing"
  | "completed"
  | "cancelled"
  | "timed_out"
  | "failed";

/** One recorded move through the scan run state machine. */
export interface ScanTransition {
  from_state: string;
  to_state: string;
  at: string;
  actor: string;
  reason: string;
}

export interface ScanEvent {
  event_id: number;
  scan_id: string;
  type: string;
  timestamp: string;
  severity: string;
  message: string;
  phase?: string | null;
  progress?: { current: number; total: number; percent: number };
  data?: Record<string, unknown>;
}

export interface ScanJob {
  id: string;
  target: string;
  profile: string;
  authorised: boolean;
  status: ScanJobStatus | string;
  progress?: number;
  created_by?: string;
  created_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  transitions?: ScanTransition[];
}

/** One raw evidence artefact a scan wrote to disk and indexed for review. */
export interface EvidenceArtifact {
  artifact_id: string;
  name: string;
  test_id?: string;
  policy_decision?: string;
  size_bytes?: number;
  available?: boolean;
}

export interface EvidenceEntry {
  finding_id: string;
  title?: string;
  source?: string;
  confidence?: string;
  tool?: string;
  observed_at?: string;
  limitations?: string;
  artifacts: EvidenceArtifact[];
}

export interface FindingMutationState {
  status: "open" | "triaged" | "in_progress" | "accepted_risk" | "false_positive" | "fixed" | "wont_fix";
  owner?: string;
  severity?: string | null;
  triage_state?: string | null;
  remediation_note?: string;
  due_date?: string | null;
  false_positive_reason?: string | null;
  accepted_risk_reason?: string | null;
  updated_at?: string;
  updated_by?: string;
}

export interface BackendFinding {
  id?: string;
  title?: string;
  description?: string;
  severity?: Severity | string;
  owasp_id?: string;
  affected_component?: string;
  evidence?: Record<string, unknown>;
  recommendation?: string;
  mitre_atlas?: string[];
  score?: number | null;
  source?: string;
  confidence?: string;
  tool?: string;
  observed_at?: string;
  limitations?: string;
  status?: FindingStatus | string;
  remediation_state?: FindingMutationState;
}

export interface FindingHistoryEntry {
  id?: number;
  scan_id?: string;
  finding_id?: string;
  previous_state: string | Record<string, unknown>;
  new_state: string | Record<string, unknown>;
  actor: string;
  timestamp: string;
  note?: string | null;
}
