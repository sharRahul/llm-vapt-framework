# Model providers

Two separate things use models in VulnoraIQ, and they are configured
independently:

1. **Imported agents** need a model to do their own work. You choose a provider
   when you deploy them in Agent Lab.
2. **The in-app assistant ("Nora")** explains findings. It is optional and runs a
   small local model in-process.

VulnoraIQ itself never calls a hosted model to perform an assessment.

## Providers for imported agents

When you deploy an agent, Agent Lab injects provider settings as environment
variables into that agent's container. It does not proxy or intercept the calls.

| Preset | API key | Default base URL | Injected variables |
| --- | --- | --- | --- |
| Ollama (local) | No | `http://host.docker.internal:11434/v1` | `OPENAI_BASE_URL`, `OPENAI_API_BASE`, `OLLAMA_HOST`, `MODEL` |
| LM Studio (local) | No | `http://host.docker.internal:1234/v1` | `OPENAI_BASE_URL`, `OPENAI_API_BASE`, `MODEL` |
| OpenRouter (hosted) | Yes | `https://openrouter.ai/api/v1` | `OPENAI_BASE_URL`, `OPENAI_API_BASE`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `MODEL` |
| Custom OpenAI-compatible | Optional | *(you supply it)* | `OPENAI_BASE_URL`, `OPENAI_API_BASE`, `OPENAI_API_KEY`, `MODEL` |
| Custom environment only | No | — | Only the variables you list |

Every preset also sets `OPENAI_MODEL`, `VULNORAIQ_LLM_MODEL`, and
`VULNORAIQ_LLM_PROVIDER` so agents that read any of those common names work
without editing.

Defaults for the presets come from the environment — `VULNORAIQ_OLLAMA_BASE_URL`,
`VULNORAIQ_LMSTUDIO_MODEL` and friends, listed in
[environment variables](../reference/environment-variables.md).

### Local providers and containers

An agent container reaches a provider running on your host through
`host.docker.internal`. Lab Mode configures that name via the host gateway; on
Linux Docker Engine you may need to confirm your Docker version supports it.

### API keys

An API key you enter is passed to the agent's container as an environment
variable and is redacted from the stored deployment record, the audit log, and
all reports. It is never written to a tracked file. See
[secrets](../security/secrets.md).

### Hybrid deployments

Deploying with `deployment_mode: hybrid` means the containerised agent depends on
an external model provider. That leaves your local lab boundary, so it requires
both an explicit provider configuration and
`authorization_acknowledged: true`. The same acknowledgement is required for
`external` mode, where you register an already-running endpoint with no container
at all.

## The in-app assistant (Nora)

Nora powers "Ask VulnoraIQ" and the plain-language finding explanations. It is
**optional**: without it, explanations fall back to deterministic templated
guidance and nothing else changes.

### What it is

- A small instruction-tuned GGUF model run in-process through
  `llama-cpp-python`, on CPU or GPU.
- Weights download once on first use and cache under
  `~/.cache/vulnoraiq/models/`. No model file is committed to this repository.
- Answers are grounded in the selected finding's evidence plus bundled OWASP LLM
  Top 10 reference notes.
- Its tools are read-only and narrow: the bundled knowledge base, an
  allowlisted documentation reader, a single SSRF-guarded size-capped HTTP GET,
  and CVE lookups.

It provides guidance for a human. It cannot reach a target, and it cannot
execute anything.

### Install

```bash
pip install -e ".[assistant]"
```

`llama-cpp-python` is a compiled package, so the wheel has to match your
hardware. VulnoraIQ loads on GPU first and falls back to CPU automatically
(`VULNORAIQ_ASSISTANT_GPU_LAYERS=auto`).

**NVIDIA GPU (CUDA 12.x):**

```bash
pip install "llama-cpp-python==0.3.31" \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 \
  --only-binary=:all:
pip install -e ".[assistant-cuda]"
```

The `assistant-cuda` extra supplies the CUDA runtime libraries through pip, so no
system CUDA toolkit is required.

**CPU only:**

```bash
pip install "llama-cpp-python==0.3.19" \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
  --only-binary=:all:
```

The `0.3.19` pin is deliberate: newer generic Windows CPU wheels have been
observed to crash with an illegal-instruction fault (`0xc000001d`) on AVX2-class
consumer CPUs during model load.

macOS Metal/MLX is **not currently supported**; on macOS the assistant runs on
CPU or is left uninstalled.

### Checking status

`GET /api/assistant/config` reports the provider, the allowed models, and whether
the local model actually loaded. In Lab Mode the assistant runs inside the
`vulnoraiq-web` container on CPU; Desktop Mode is where it can use the host GPU.

## Related

- [Agents guide](agents.md)
- [Findings and evidence](findings.md)
- [Environment variables](../reference/environment-variables.md)
