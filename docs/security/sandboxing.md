# Sandboxing and isolation

VulnoraIQ runs code it did not write: agent projects you import, and prebuilt
agent images you deploy. This page states exactly what isolates them and — just
as importantly — what does not.

## The containers involved

| Container | What it is | Trust |
| --- | --- | --- |
| `vulnoraiq-web` (Lab Mode only) | VulnoraIQ itself. | Trusted. |
| `vulnoraiq-agent-lab-<project>` | An agent built from an imported project. | **Untrusted.** |
| `vulnoraiq-agent-<id>` | An agent from a prebuilt image. | **Untrusted.** |

In Desktop Mode there is no `vulnoraiq-web` container: VulnoraIQ runs as a host
process and Docker is used only for the agents.

## Controls applied to agent containers

Every agent container is started with:

- `--security-opt no-new-privileges:true` — no privilege escalation inside.
- `--cap-drop ALL` — every Linux capability dropped.
- an explicit Docker network (`VULNORAIQ_AGENT_NETWORK`), never host networking.
- port publishing bound to `127.0.0.1` only, so an intentionally weak assessment
  target is never reachable from the rest of the network.
- optional `--memory` and `--cpus` limits supplied at deploy time.
- GPU access only when explicitly requested (`gpu.mode` of `all` or `device`).

Agent Lab additionally:

- refuses git clones from hosts outside `VULNORAIQ_AGENT_LAB_ALLOWED_GIT_HOSTS`,
  and refuses URLs with embedded credentials.
- enforces size and file-count caps on imports, and rejects archive entries with
  absolute paths or `..` traversal segments (zip-slip).
- resolves every project path against the Agent Lab root and refuses anything
  that escapes it.
- health-gates registration: a container that never serves HTTP, or crash-loops,
  is removed instead of becoming a broken target.

## The Docker socket

In Lab Mode, `docker-compose.yml` mounts `/var/run/docker.sock` into
`vulnoraiq-web` so Agent Lab can build and run agent containers. This is the
central trust decision in the design, and it is deliberate:

**Access to the Docker socket is equivalent to root on the host.** Anyone who can
reach the VulnoraIQ API with `manage_runtime` permission can start containers on
your machine.

That is why:

- the console is published on `127.0.0.1` only;
- Agent Lab endpoints require the `manage_runtime` permission, which only the
  admin role holds;
- every Agent Lab write requires a valid CSRF token;
- production mode refuses `local_admin` and demands a real admin token.

Do not expose a VulnoraIQ deployment with Agent Lab enabled on a shared network
without token auth, TLS, a trusted reverse proxy, audit retention, and a
recorded risk decision.

## Command execution

Every external command — Docker and git alike — is executed as an argument
array through a single boundary (`webui/docker_cli.py` for Docker,
`_run_command` for git). No shell is involved, so project ids, image names, URLs
and other user-supplied values cannot inject commands. Every invocation is
bounded by a timeout, and failures surface as typed errors carrying the tool's
own stderr.

A language model cannot reach these boundaries. VulnoraIQ has no path from model
output to command execution: the assistant produces text for a human, and
assessment payloads are data sent to a target over HTTP.

## Network scope

An assessment request is only sent after the target URL passes scope validation:

- the scheme must be `http` or `https`, and the URL must not embed credentials;
- a configured allowlist (`VULNORAIQ_ALLOWED_TARGET_HOSTS`, a safety profile's
  `allowed_hosts`, or the target's own `allowed_host_pattern`) is enforced;
- with no allowlist and no explicit `allow_external`, the host must resolve
  entirely to loopback, private, or link-local addresses.

Resolution — rather than matching on the hostname text — is what lets Docker Lab
Mode reach an agent by its container DNS name while still refusing a public host
named something like `api.example.internal`.

## What this does not cover

- **User namespaces.** Agent containers run as whatever user their image
  defines. Capability drop and `no-new-privileges` limit what that user can do,
  but this is not a hostile-multi-tenant boundary.
- **seccomp/AppArmor beyond Docker's defaults.** Docker's default seccomp profile
  applies; VulnoraIQ does not ship a tighter one.
- **Outbound network egress from an agent.** An agent container can reach
  whatever its Docker network permits, including a model provider on the
  internet. That is required for agents that call hosted models.
- **Reviewing what you import.** VulnoraIQ builds and runs the code you give it.
  Read it first.

Treat Agent Lab as a controlled local lab for code you own or are authorised to
run — not as a malware detonation sandbox.

## Related

- [Security model](security-model.md)
- [Agents guide](../guides/agents.md)
- [Lab Mode](../guides/lab-mode.md)
