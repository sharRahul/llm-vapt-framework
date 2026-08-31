"""In-process small language model for the VulnoraIQ assistant.

This is an optional, self-contained backend that runs a small instruction-tuned
GGUF model locally through ``llama-cpp-python`` (CPU or GPU). It is *not* tied to
Ollama or any external service: weights are downloaded once on first use and
cached, so the assistant works offline afterwards.

The whole module degrades gracefully: if the ``vulnoraiq[assistant]`` extra is
not installed or the weights cannot be fetched, :class:`LocalAssistantModel`
reports itself unavailable and callers fall back to templated guidance.

Configuration (all optional, via environment):

- ``VULNORAIQ_ASSISTANT_MODEL_PATH``  explicit path to a local ``.gguf`` file
  (use this to point at a model you fine-tuned yourself).
- ``VULNORAIQ_ASSISTANT_MODEL_DIR``   cache directory for downloaded weights.
- ``VULNORAIQ_ASSISTANT_MODEL_REPO``  HuggingFace repo id for the default model.
- ``VULNORAIQ_ASSISTANT_MODEL_FILE``  GGUF filename within that repo.
- ``VULNORAIQ_ASSISTANT_MODEL_URL``   direct download URL override.
- ``VULNORAIQ_ASSISTANT_AUTODOWNLOAD`` set ``false`` to disable first-run fetch.
- ``VULNORAIQ_ASSISTANT_GPU_LAYERS``  ``auto`` (default), ``0`` (CPU), or a layer
  count / ``-1`` to offload everything to the GPU (needs a CUDA/Metal build).
- ``VULNORAIQ_ASSISTANT_CTX``         context window (default 4096).
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import threading
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_MODEL_REPO = os.getenv("VULNORAIQ_ASSISTANT_MODEL_REPO", "Qwen/Qwen2.5-0.5B-Instruct-GGUF")
DEFAULT_MODEL_FILE = os.getenv("VULNORAIQ_ASSISTANT_MODEL_FILE", "qwen2.5-0.5b-instruct-q4_k_m.gguf")
# Repo-local fine-tuned Nora build, preferred over the HF download when present
# (see LocalAssistantModel.model_path). The shipped quant from model/assistant-output.
DEFAULT_LOCAL_MODEL_FILE = os.getenv("VULNORAIQ_ASSISTANT_LOCAL_MODEL_FILE", "nora-1.7b-Q4_K_M.gguf")
DEFAULT_MODEL_URL = os.getenv("VULNORAIQ_ASSISTANT_MODEL_URL", "").strip()
_DLL_DIRECTORIES: list[object] = []


class ModelUnavailable(RuntimeError):
    """Raised when the optional model runtime or weights are not available."""


def _truthy(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def cache_dir() -> Path:
    base = os.getenv("VULNORAIQ_ASSISTANT_MODEL_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "vulnoraiq", "models"
    )
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _register_windows_dll_dir(path: Path) -> None:
    if os.name != "nt" or not path.is_dir():
        return
    resolved = str(path.resolve())
    try:
        handle = os.add_dll_directory(resolved)
    except (AttributeError, OSError):
        handle = None
    if handle is not None:
        _DLL_DIRECTORIES.append(handle)
    current_path = os.environ.get("PATH", "")
    parts = current_path.split(os.pathsep) if current_path else []
    if resolved not in parts:
        os.environ["PATH"] = resolved + os.pathsep + current_path if current_path else resolved


def _register_nvidia_pip_runtime() -> None:
    """Register CUDA runtime DLLs shipped by the ``nvidia-*-cu12`` pip packages.

    The prebuilt CUDA ``llama-cpp-python`` wheels dynamically link cudart/cublas/
    nvrtc. When CUDA is provided through pip (``nvidia-cuda-runtime-cu12``,
    ``nvidia-cublas-cu12``) instead of a system CUDA toolkit, those DLLs live in
    ``site-packages/nvidia/<component>/bin`` and are not on the default search
    path, so ``ggml-cuda.dll`` fails to load and GPU offload silently falls back
    to CPU. Add each component's ``bin`` directory before importing llama.cpp.
    """
    try:
        import nvidia
    except Exception:
        return
    for root in getattr(nvidia, "__path__", []):
        try:
            components = sorted(Path(root).iterdir())
        except OSError:
            continue
        for component in components:
            _register_windows_dll_dir(component / "bin")


def _prepare_windows_llama_runtime() -> None:
    """Expose bundled DLL directories before importing llama.cpp on Windows."""
    if os.name != "nt":
        return
    for name, value in os.environ.items():
        if name.startswith("CUDA_PATH") and value:
            _register_windows_dll_dir(Path(value) / "bin")
    _register_nvidia_pip_runtime()
    try:
        spec = importlib.util.find_spec("llama_cpp")
    except Exception:
        spec = None
    if spec and spec.origin:
        _register_windows_dll_dir(Path(spec.origin).resolve().parent / "lib")
    try:
        import torch
    except Exception:
        return
    _register_windows_dll_dir(Path(torch.__file__).resolve().parent / "lib")


def runtime_available() -> bool:
    """True if ``llama-cpp-python`` is importable."""
    try:
        _prepare_windows_llama_runtime()
        import llama_cpp  # noqa: F401
    except Exception:
        return False
    return True


class LocalAssistantModel:
    """Lazily-loaded singleton wrapper around a local GGUF chat model."""

    _instance: LocalAssistantModel | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        # The concrete type is llama_cpp.Llama, which is an optional dependency.
        self._llm: Any = None
        self._load_lock = threading.Lock()
        # A llama.cpp context holds mutable decode state and is NOT safe for
        # concurrent calls; overlapping requests crash with "llama_decode
        # returned -1". The UI fires several explain/chat calls at once (e.g. the
        # Workspace auto-explains findings), so serialise generation here.
        self._gen_lock = threading.Lock()
        self._load_error: str | None = None

    @classmethod
    def instance(cls) -> LocalAssistantModel:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def model_path(self) -> Path:
        explicit = os.getenv("VULNORAIQ_ASSISTANT_MODEL_PATH", "").strip()
        if explicit:
            return Path(explicit)
        # Prefer the repo-local fine-tuned Nora GGUF when it is present, so a checkout
        # runs the trained model out of the box instead of silently downloading the
        # generic Qwen base. Env override above still wins; HF download below is the
        # last resort (and only fires when no local Nora build exists).
        local_nora = (
            Path(__file__).resolve().parent.parent
            / "model" / "assistant-output" / DEFAULT_LOCAL_MODEL_FILE
        )
        if local_nora.is_file():
            return local_nora
        return cache_dir() / DEFAULT_MODEL_FILE

    def status(self) -> dict[str, object]:
        path = self.model_path()
        return {
            "runtime_installed": runtime_available(),
            "model_present": path.exists(),
            "model_path": str(path),
            "autodownload": _truthy(os.getenv("VULNORAIQ_ASSISTANT_AUTODOWNLOAD"), True),
            "load_error": self._load_error,
        }

    def available(self) -> bool:
        """Available without triggering a (possibly large) download."""
        return runtime_available() and (
            self.model_path().exists() or _truthy(os.getenv("VULNORAIQ_ASSISTANT_AUTODOWNLOAD"), True)
        )

    def ensure_model(self) -> Path:
        path = self.model_path()
        if path.exists():
            return path
        if not _truthy(os.getenv("VULNORAIQ_ASSISTANT_AUTODOWNLOAD"), True):
            raise ModelUnavailable(f"assistant model not found at {path} and autodownload is disabled")
        url = DEFAULT_MODEL_URL or (
            f"https://huggingface.co/{DEFAULT_MODEL_REPO}/resolve/main/{DEFAULT_MODEL_FILE}?download=true"
        )
        tmp = path.with_name(path.name + ".part")
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "VulnoraIQ-Assistant"})
            with urllib.request.urlopen(request, timeout=120) as resp, open(tmp, "wb") as handle:
                shutil.copyfileobj(resp, handle)
            tmp.replace(path)
        except Exception as exc:  # network / disk failure -> stay graceful
            tmp.unlink(missing_ok=True)
            raise ModelUnavailable(f"failed to download assistant model: {exc}") from exc
        return path

    def _load(self):
        if self._llm is not None:
            return self._llm
        with self._load_lock:
            if self._llm is not None:
                return self._llm
            try:
                _prepare_windows_llama_runtime()
                import llama_cpp
            except Exception as exc:
                raise ModelUnavailable(
                    "llama-cpp-python is not installed; install the optional 'vulnoraiq[assistant]' extra"
                ) from exc
            path = self.ensure_model()
            n_ctx = int(os.getenv("VULNORAIQ_ASSISTANT_CTX", "4096"))
            gpu_setting = os.getenv("VULNORAIQ_ASSISTANT_GPU_LAYERS", "auto").strip().lower()
            attempts: list[int] = []
            if gpu_setting in {"", "auto"}:
                attempts = [-1, 0]  # try GPU offload, fall back to CPU
            else:
                try:
                    attempts = [int(gpu_setting)]
                except ValueError:
                    attempts = [0]
            last_exc: Exception | None = None
            for layers in attempts:
                try:
                    self._llm = llama_cpp.Llama(
                        model_path=str(path), n_ctx=n_ctx, n_gpu_layers=layers, verbose=False
                    )
                    self._load_error = None
                    return self._llm
                except Exception as exc:  # GPU build missing etc. -> retry CPU
                    last_exc = exc
            self._load_error = str(last_exc)
            raise ModelUnavailable(f"failed to load assistant model: {last_exc}") from last_exc

    def generate(self, messages: list[dict[str, str]], *, temperature: float, max_tokens: int) -> str:
        llm = self._load()
        with self._gen_lock:
            result = llm.create_chat_completion(
                messages=messages, temperature=max(0.0, min(1.0, temperature)), max_tokens=max_tokens
            )
        return str(result["choices"][0]["message"]["content"]).strip()
