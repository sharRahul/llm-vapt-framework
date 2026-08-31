"""The VulnoraIQ web server: core assessment API plus assistant and Agent Lab.

This is the single entry point for both run modes. Desktop Mode starts it
directly on the host; Docker Lab Mode starts it inside the ``vulnoraiq-web``
container. It layers the assistant and Agent Lab routes onto the core handler in
:mod:`webui.hosted_server`, so both modes serve exactly the same API surface.
"""

from __future__ import annotations

import os
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from core import runtime_targets
from integrations import cve_lookup
from webui import hosted_server
from webui.agent_lab import (
    analyze_agent_project,
    delete_project,
    deploy_agent_project,
    generate_dockerfile_for_project,
    import_archive_project,
    import_git_project,
    list_agent_projects,
    list_deployments,
    provider_presets,
    remove_deployment,
)
from webui.assistant import AssistantOrchestrator
from webui.auth import AuthPrincipal
from webui.hosted_server import AUTH_MANAGER, HostedWebUiHandler
from webui.payload import dict_field
from webui.web_security import audit_event, csrf_tokens

ASSISTANT = AssistantOrchestrator()


def _is_desktop_mode() -> bool:
    return os.getenv("VULNORAIQ_RUN_MODE", "").strip().lower() in {"desktop", "native"}


class VulnoraIQWebHandler(HostedWebUiHandler):
    """Core handler extended with the assistant and Agent Lab endpoints."""

    # --- shared request guards -------------------------------------------------

    def _authorised_principal(
        self, client_ip: str, method: str, path: str, request_id: str, permission: str
    ) -> AuthPrincipal | None:
        """Authenticate, rate-limit, and authorise in one step.

        Returns ``None`` after having already written the failure response, so
        callers only have to check for ``None``.
        """
        principal = self._require_principal(client_ip, method, path, request_id)
        if not principal or not self._check_rate_limit(principal, client_ip):
            return None
        if not AUTH_MANAGER.can(principal, permission):
            self._forbidden()
            return None
        return principal

    def _mutating_principal(
        self, client_ip: str, path: str, request_id: str, permission: str
    ) -> AuthPrincipal | None:
        """As above, plus the CSRF check every state-changing route requires."""
        principal = self._authorised_principal(client_ip, "POST", path, request_id, permission)
        if principal is None:
            return None
        if not csrf_tokens.validate(self._session_key(principal), self.headers.get("X-CSRF-Token")):
            self._send_error_response(HTTPStatus.FORBIDDEN, "invalid or missing CSRF token")
            return None
        return principal

    # --- reads ------------------------------------------------------------------

    def _do_GET_routes(self, path: str, client_ip: str, request_id: str) -> None:
        clean_path = urlparse(path).path
        if clean_path in {"/agent-lab", "/agent-lab/"}:
            # The former static Agent Lab is intentionally retired. Keep old
            # bookmarks useful without preserving a second, divergent UI.
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/#/projects")
            self.send_header("Content-Length", "0")
            self._security_headers()
            self.end_headers()
            return
        if clean_path == "/api/assistant/config":
            if self._authorised_principal(client_ip, "GET", clean_path, request_id, "view_scans") is None:
                return
            self._send_json(ASSISTANT.available_config())
            return
        if clean_path.startswith("/api/agent-lab"):
            self._handle_agent_lab_get(clean_path, client_ip, request_id)
            return
        super()._do_GET_routes(path, client_ip, request_id)

    def _handle_agent_lab_get(self, clean_path: str, client_ip: str, request_id: str) -> None:
        principal = self._authorised_principal(client_ip, "GET", clean_path, request_id, "manage_runtime")
        if principal is None:
            return
        if clean_path == "/api/agent-lab":
            cfg = hosted_server.load_config()
            self._send_json(
                {
                    "experimental": True,
                    "run_mode": os.getenv("VULNORAIQ_RUN_MODE", "docker_lab"),
                    "provider_presets": provider_presets(),
                    "projects": list_agent_projects(),
                    "deployments": list_deployments(),
                    "profiles": {
                        key: {"description": value.get("description", "")}
                        for key, value in cfg.get("profiles", {}).items()
                    },
                    "targets": cfg.get("targets", {}),
                }
            )
            return
        if clean_path == "/api/agent-lab/projects":
            self._send_json({"projects": list_agent_projects()})
            return
        if clean_path == "/api/agent-lab/deployments":
            self._send_json({"deployments": list_deployments()})
            return
        if clean_path.startswith("/api/agent-lab/projects/"):
            project_id = self._path_segment(clean_path, 3)
            if clean_path.endswith("/analyze"):
                self._send_json(analyze_agent_project(project_id))
                return
            if clean_path.endswith("/dockerfile"):
                dockerfile = generate_dockerfile_for_project(project_id)
                self._send_json({"exists": bool(dockerfile), "dockerfile": dockerfile or ""})
                return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    # --- writes -----------------------------------------------------------------

    def _do_POST_routes(self, path: str, client_ip: str, request_id: str) -> None:
        clean_path = urlparse(path).path
        if clean_path in {"/api/assistant/chat", "/api/assistant/explain", "/api/findings/cve"}:
            self._handle_analysis_post(clean_path, client_ip, request_id)
            return
        if clean_path.startswith("/api/agent-lab/"):
            self._handle_agent_lab_post(clean_path, client_ip, request_id)
            return
        super()._do_POST_routes(path, client_ip, request_id)

    def _handle_analysis_post(self, clean_path: str, client_ip: str, request_id: str) -> None:
        principal = self._mutating_principal(client_ip, clean_path, request_id, "view_scans")
        if principal is None:
            return
        payload = self._read_json()
        if clean_path == "/api/assistant/chat":
            response = ASSISTANT.chat(payload, actor=principal.username)
            detail = f"provider={response.get('provider')} model={response.get('model')}"
            event = "assistant_chat"
        else:
            finding = dict_field(payload, "finding")
            if clean_path == "/api/assistant/explain":
                response = ASSISTANT.explain_finding(finding)
                detail = f"backend={response.get('backend')}"
                event = "assistant_explain"
            else:
                response = cve_lookup.lookup_for_finding(finding)
                detail = f"matches={response.get('match_count')} novel={response.get('candidate_novel')}"
                event = "finding_cve_lookup"
        audit_event(event, principal, request_id, client_ip, "POST", clean_path, 200, detail)
        self._send_json(response)

    def _handle_agent_lab_post(self, clean_path: str, client_ip: str, request_id: str) -> None:
        principal = self._mutating_principal(client_ip, clean_path, request_id, "manage_runtime")
        if principal is None:
            return
        payload = self._read_json()
        try:
            if clean_path == "/api/agent-lab/import/git":
                result = import_git_project(
                    str(payload.get("url") or ""),
                    project_id=str(payload.get("project_id") or "") or None,
                    branch=str(payload.get("branch") or "") or None,
                )
                audit_event(
                    "agent_lab_import_git", principal, request_id, client_ip, "POST", clean_path, 200, result.project_id
                )
                self._send_json({"imported": True, **result.__dict__})
                return
            if clean_path == "/api/agent-lab/import/archive":
                result = import_archive_project(
                    str(payload.get("archive_base64") or ""), str(payload.get("project_id") or "")
                )
                audit_event(
                    "agent_lab_import_archive",
                    principal,
                    request_id,
                    client_ip,
                    "POST",
                    clean_path,
                    200,
                    result.project_id,
                )
                self._send_json({"imported": True, **result.__dict__})
                return
            if clean_path.startswith("/api/agent-lab/projects/") and clean_path.endswith("/deploy"):
                project_id = self._path_segment(clean_path, 3)
                deployment = deploy_agent_project(project_id, payload, self._save_target_fn())
                audit_event(
                    "agent_lab_deploy",
                    principal,
                    request_id,
                    client_ip,
                    "POST",
                    clean_path,
                    200,
                    deployment.project_id,
                )
                self._send_json({"deployed": True, **deployment.__dict__})
                return
            if clean_path.startswith("/api/agent-lab/projects/") and clean_path.endswith("/delete"):
                project_id = self._path_segment(clean_path, 3)
                deleted = delete_project(project_id)
                audit_event(
                    "agent_lab_delete_project", principal, request_id, client_ip, "POST", clean_path, 200, project_id
                )
                self._send_json({"deleted": deleted, "project_id": project_id})
                return
            if clean_path.startswith("/api/agent-lab/deployments/") and clean_path.endswith("/remove"):
                identifier = self._path_segment(clean_path, 3)
                removal = remove_deployment(identifier)
                audit_event(
                    "agent_lab_remove_deployment",
                    principal,
                    request_id,
                    client_ip,
                    "POST",
                    clean_path,
                    200,
                    identifier,
                )
                self._send_json(removal)
                return
        except RuntimeError as exc:
            # Docker/git failures are upstream problems, not VulnoraIQ faults.
            self._send_error_response(HTTPStatus.BAD_GATEWAY, str(exc))
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    # --- helpers ----------------------------------------------------------------

    @staticmethod
    def _path_segment(clean_path: str, index: int) -> str:
        parts = [unquote(item) for item in clean_path.split("/") if item]
        return parts[index] if index < len(parts) else ""

    def _save_target_fn(self):
        """Return the target-registration function for the active run mode.

        Agent Lab computes the reachable base URL itself (container DNS in
        Docker Lab Mode, published loopback port in Desktop Mode), so the save
        function must not rewrite it. Desktop Mode only tags the environment so
        the target is recognisable in the workspace.
        """
        if not _is_desktop_mode():
            return runtime_targets.save

        def save_desktop_target(target_id: str, config: dict):
            return runtime_targets.save(target_id, {**config, "environment": "agent_lab_desktop"})

        return save_desktop_target


def create_server(host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    return hosted_server.create_server(host, port, VulnoraIQWebHandler)


def main() -> None:
    hosted_server.serve(VulnoraIQWebHandler)


__all__ = ["VulnoraIQWebHandler", "create_server", "main"]


if __name__ == "__main__":
    main()
