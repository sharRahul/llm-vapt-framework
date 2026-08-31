from __future__ import annotations

import threading

from webui.web_security import MetricsRegistry, metrics


def test_metrics_counters_increment() -> None:
    registry = MetricsRegistry()
    registry.increment("test_counter")
    registry.increment("test_counter")

    assert registry.snapshot()["test_counter"] == 2


def test_metrics_snapshot_is_a_copy() -> None:
    registry = MetricsRegistry()
    registry.increment("counter")
    snapshot = registry.snapshot()
    snapshot["counter"] = 999

    assert registry.snapshot()["counter"] == 1


def test_metrics_exposition_includes_scan_gauges() -> None:
    """The /metrics body must carry scan concurrency, not just counters."""
    from webui import hosted_server

    metrics.increment("scans_created")
    body = _render_metrics(hosted_server)

    assert "vulnoraiq_active_scans" in body
    assert "vulnoraiq_queued_scans" in body
    assert "vulnoraiq_scans_created_total" in body


def _render_metrics(hosted_server) -> str:
    captured: list[bytes] = []

    class Recorder(hosted_server.HostedWebUiHandler):
        def __init__(self) -> None:  # noqa: D107 - bypasses socket setup on purpose
            pass

        def send_response(self, *args, **kwargs) -> None:
            pass

        def send_header(self, *args, **kwargs) -> None:
            pass

        def end_headers(self) -> None:
            pass

        def _client_ip(self) -> str:
            return "127.0.0.1"

        @property
        def wfile(self):
            class Sink:
                @staticmethod
                def write(data: bytes) -> None:
                    captured.append(data)

            return Sink()

    Recorder()._serve_metrics()
    return b"".join(captured).decode("utf-8")


def test_metrics_registry_is_thread_safe() -> None:
    registry = MetricsRegistry()
    errors: list[Exception] = []

    def increment() -> None:
        try:
            for _ in range(100):
                registry.increment("concurrent")
        except Exception as exc:  # pragma: no cover - only fires on a real race
            errors.append(exc)

    threads = [threading.Thread(target=increment) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert registry.snapshot()["concurrent"] == 1000
