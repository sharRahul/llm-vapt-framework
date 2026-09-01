from __future__ import annotations

import threading
import time


class ScanCancelled(Exception):
    """Raised inside a run when an operator asked it to stop."""


class ScanTimedOut(Exception):
    """Raised inside a run when it exceeded its whole-run budget."""


class CancellationToken:
    """Cooperative stop signal carried through a scan run.

    "Stop sending traffic to that target, now" is a safety control, so the token
    is checked at the natural boundaries — between modules and between payloads —
    which bounds a cancellation to at most one in-flight request.
    """

    def __init__(self, budget_seconds: float | None = None) -> None:
        self._event = threading.Event()
        self._reason = ""
        self._actor = ""
        self._budget_seconds = budget_seconds
        self._started = time.monotonic()

    def cancel(self, reason: str = "cancelled by operator", actor: str = "unknown") -> None:
        self._reason = reason
        self._actor = actor
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def actor(self) -> str:
        return self._actor

    def expired(self) -> bool:
        return self._budget_seconds is not None and (time.monotonic() - self._started) >= self._budget_seconds

    def raise_if_stopped(self) -> None:
        """Check both stop conditions at a safe boundary."""
        if self._event.is_set():
            raise ScanCancelled(self._reason or "cancelled by operator")
        if self.expired():
            raise ScanTimedOut(f"scan exceeded its {self._budget_seconds:g}s budget")


class CancellationRegistry:
    """Process-local map of run id to token, so an API call can reach a thread."""

    def __init__(self) -> None:
        self._tokens: dict[str, CancellationToken] = {}
        self._lock = threading.RLock()

    def create(self, run_id: str, budget_seconds: float | None = None) -> CancellationToken:
        token = CancellationToken(budget_seconds=budget_seconds)
        with self._lock:
            self._tokens[run_id] = token
        return token

    def get(self, run_id: str) -> CancellationToken | None:
        with self._lock:
            return self._tokens.get(run_id)

    def get_or_create(self, run_id: str, budget_seconds: float | None = None) -> CancellationToken:
        """Return the existing token for a run, or register a new one.

        A run can be cancelled between being queued and being picked up by a
        worker, so the worker must adopt whatever token already exists rather
        than replacing it and discarding the cancellation.
        """
        with self._lock:
            token = self._tokens.get(run_id)
            if token is None:
                token = CancellationToken(budget_seconds=budget_seconds)
                self._tokens[run_id] = token
            return token

    def cancel(self, run_id: str, reason: str = "cancelled by operator", actor: str = "unknown") -> bool:
        with self._lock:
            token = self._tokens.get(run_id)
        if token is None:
            return False
        token.cancel(reason, actor)
        return True

    def discard(self, run_id: str) -> None:
        with self._lock:
            self._tokens.pop(run_id, None)
