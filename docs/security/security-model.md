# Safety model

VulnoraIQ is a controlled AI security assessment lab. Use it only against systems you own or are explicitly authorised to assess.

The current safety model has three layers:

1. **Scope controls** — no default target; all configured targets require explicit authorisation.
2. **Runtime controls** — Docker lab targets use private service names, bounded request limits, safety profiles, rate limits, timeouts, response-size limits, and explicit Agent Lab controls when imported agents are built/run locally.
3. **Evidence controls** — reports and evidence are written to controlled paths with redaction and artifact path protection.

## Docker lab controls

The current default lab uses Docker Compose:

- private `vulnoraiq-lab` bridge network;
- no host networking;
- no privileged containers;
- non-root application users;
- capability drop and `no-new-privileges`;
- Docker-only service-name targets in `config/targets.docker.yaml`;
- host allowlists through safety profiles;
- bounded request count, concurrency, size, timeout, and rate limits;
- sanitized reports and evidence with secret redaction;
- reports, evidence, audit logs, Agent Lab imports, and jobs under `/data`.

## Experimental Agent Lab controls

Agent Lab is an experimental local-lab feature for importing, building, running, and testing real AI-agent projects.

The current implementation intentionally mounts the Docker socket so the WebUI container can run Docker build/run commands for imported projects. This is a higher-trust local-lab control surface, not a hardened multi-tenant security boundary.

Agent Lab adds these controls:

- WebUI/API access requires a principal with `manage_runtime` permission;
- all write actions require CSRF protection;
- Git import accepts only configured HTTPS hosts and rejects embedded credentials;
- ZIP import uses size, file-count, and path traversal checks;
- project IDs containing demo, mock, fake, or fixture are rejected in normal runtime;
- provider API keys are passed to launched containers as runtime environment variables and redacted from deployment metadata;
- launched containers receive `--security-opt no-new-privileges:true` and `--cap-drop ALL`;
- generated runtime targets require authorisation and use `environment: agent_lab`.

Keep the default WebUI loopback-only for Agent Lab use. Do not expose Agent Lab on a shared/internal-server deployment without production auth, reverse-proxy/TLS controls, audit retention, and an explicit risk decision.

## Authorisation gate

All scans require one of these:

- CLI: pass `--authorised`.
- WebUI: confirm the authorisation checklist before scan launch.
- Agent Lab: use the generated runtime target only for systems and agent code you own or are explicitly authorised to assess.

Authorisation means the assessor owns the target or has written permission to assess it. VulnoraIQ is not intended for unapproved assessment of third-party systems.

## Fail-closed cases

The current safety posture blocks or fails closed for:

- missing authorisation on configured targets;
- unsupported URL schemes;
- public or external hosts when the selected safety profile does not allow them;
- oversized requests or responses;
- missing Docker lab configuration for Docker lab mode;
- malformed JSON/API requests;
- unsafe artifact path traversal;
- missing production auth configuration when `VULNORAIQ_ENV=production`;
- secrets detected in persisted artifacts or evidence paths where redaction should have applied;
- unsafe Agent Lab project IDs or archive paths;
- Agent Lab Git hosts that are not in the configured allow-list.

## Evidence boundary

VulnoraIQ collects framework evidence for scanner/reporting purposes. Human review is required before sharing reports or treating a finding as confirmed.

Do not store real credentials, sensitive personal data, production prompts, or business-confidential responses in test fixtures. For real authorised targets, review generated evidence and reports before distribution.

## Not a permission or assurance grant

The safety model reduces accidental misuse and unsafe local testing paths. It does not provide legal authorisation, certified VAPT-grade assurance, or proof that every real-world vulnerability class is detectable.
