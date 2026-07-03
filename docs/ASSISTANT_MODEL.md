# VulnoraIQ assistant model

"Ask VulnoraIQ" and the AI finding explanations are powered by a small,
self-contained language model that runs **inside VulnoraIQ** — not through
Ollama or any external API. It is an optional helper agent: it summarises
findings, explains AI/LLM vulnerabilities, and suggests mitigations. It never
applies changes to a target; it provides guidance for a human reviewer.

The model is **optional**. If it is not installed, the assistant degrades
gracefully to deterministic templated guidance, and nothing else breaks.

## How it works

- Runs a small instruction-tuned **GGUF** model in-process via
  [`llama-cpp-python`](https://github.com/abetlen/llama-cpp-python) on **CPU or
  GPU**.
- Weights are **downloaded once on first use** and cached under
  `~/.cache/vulnoraiq/models/`, so the repository stays small and the assistant
  works offline afterwards.
- Answers are **grounded** in VulnoraIQ's bundled OWASP LLM Top-10 notes (a
  dependency-free keyword retriever) plus the selected finding's evidence.
- Tools (skills): **knowledge base** (bundled docs), **web_fetch** (a single,
  SSRF-guarded, size-capped HTTP GET so it can look something up when it does not
  know), **read_docs** (read-only, allowlisted to the docs folder), and
  **cve_lookup** (auto-queries NVD + OSV for matching CVE records when a finding
  has package or keyword information).

## Install

```bash
pip install -e .[assistant]      # adds llama-cpp-python
```

The default model (`Qwen/Qwen2.5-0.5B-Instruct-GGUF`, ~0.4 GB) downloads on first
use. No model file is committed to the repository.

### CPU vs GPU and wheel compatibility

`llama-cpp-python` is a compiled package, so the wheel must match your hardware.
The assistant loads on **GPU by default** (`n_gpu_layers=-1`) and falls back to
CPU automatically (`VULNORAIQ_ASSISTANT_GPU_LAYERS=auto`).

- **GPU (recommended, NVIDIA CUDA 12.x):**

  ```bash
  pip install "llama-cpp-python==0.3.31" --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --only-binary=:all:
  pip install -e ".[assistant-cuda]"
  ```

  The CUDA wheel dynamically links `cudart`/`cublas`/`nvrtc`. The `assistant-cuda`
  extra installs those through the `nvidia-*-cu12` pip packages, so **no system
  CUDA toolkit is required**. On Windows, `webui/assistant_llm.py` adds
  `site-packages/nvidia/*/bin` to the DLL search path before importing llama.cpp,
  so the GPU wheel finds its runtime with no manual `PATH` setup. Verify with
  `verbose=True`: the log shows `found 1 CUDA devices` and layers `assigned to
  device CUDA0`.
- **CPU (no NVIDIA GPU):**
  `pip install "llama-cpp-python==0.3.19" --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --only-binary=:all:`.
- **Older / AVX2-class CPUs** (symptom: `Windows Error 0xc000001d` /
  `Illegal instruction` on load): generic prebuilt wheels — including newer
  Windows CPU wheels such as `0.3.30` — assume an instruction set the CPU lacks.
  Pin `0.3.19` from the `cpu` index above, build for your CPU
  (`CMAKE_ARGS="-DLLAMA_AVX2=OFF" pip install llama-cpp-python --no-binary :all:`,
  needs a C/C++ toolchain), or use the GPU wheel.

When the runtime or weights are unavailable, VulnoraIQ logs the reason and uses
templated guidance — the WebUI keeps working.

## Configuration (environment)

| Variable | Purpose | Default |
| --- | --- | --- |
| `VULNORAIQ_ASSISTANT_MODEL_PATH` | Use a specific local `.gguf` (e.g. one you fine-tuned) | unset |
| `VULNORAIQ_ASSISTANT_MODEL_DIR` | Cache directory for downloaded weights | `~/.cache/vulnoraiq/models` |
| `VULNORAIQ_ASSISTANT_MODEL_REPO` / `_FILE` | Default HuggingFace repo / GGUF filename | Qwen2.5-0.5B-Instruct |
| `VULNORAIQ_ASSISTANT_MODEL_URL` | Direct download URL override | derived from repo/file |
| `VULNORAIQ_ASSISTANT_AUTODOWNLOAD` | Allow first-run download | `true` |
| `VULNORAIQ_ASSISTANT_GPU_LAYERS` | `auto`, `0` (CPU), or a layer count / `-1` (all GPU) | `auto` |
| `VULNORAIQ_ASSISTANT_CTX` | Context window | `4096` |
| `VULNORAIQ_ASSISTANT_READ_ROOT` | Allowlisted root for the `read_docs` tool | `docs/` |
| `VULNORAIQ_CVE_TIMEOUT` | Timeout (seconds) for CVE API calls | `12` |

## Training your own model (16 GB GPU)

You can fine-tune a small base model on cyber/AI-security material and drop the
result in as a GGUF — no change to VulnoraIQ code:

1. Pick a small base that fits LoRA/QLoRA training on 16 GB (e.g. Qwen2.5-0.5B/1.5B,
   Llama-3.2-1B/3B, Gemma-2-2B).
2. Fine-tune with QLoRA (e.g. `unsloth` or `transformers` + `peft` + `bitsandbytes`)
   on your AI-security dataset; 4-bit QLoRA keeps a 1–3B model within 16 GB.
3. Merge the adapter and convert to GGUF with `llama.cpp`'s `convert_hf_to_gguf.py`,
   then quantize (e.g. `q4_k_m`).
4. Point VulnoraIQ at it: `VULNORAIQ_ASSISTANT_MODEL_PATH=/path/to/your-model.gguf`.

The assistant keeps the same tools (knowledge base, `web_fetch`, `read_docs`,
`cve_lookup`), so a model that does not know an answer can still fetch a
reference URL the user provides or look up known CVEs. The training dataset
(`prepare_dataset.py`) now includes examples where the model references
live CVE data from the lookup. Custom training is a follow-up to this
foundation, not a prerequisite.
