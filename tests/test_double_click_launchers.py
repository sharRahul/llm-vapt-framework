from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_LAUNCHERS = [
    ROOT / "launch-vulnoraiq-webui.bat",
    ROOT / "launch-vulnoraiq-webui.command",
    ROOT / "launch-vulnoraiq-webui.sh",
]
DOCKER_LAB_LAUNCHERS = [
    ROOT / "launch-vulnoraiq-docker-lab.bat",
    ROOT / "launch-vulnoraiq-docker-lab.command",
    ROOT / "launch-vulnoraiq-docker-lab.sh",
]


def test_platform_launchers_start_desktop_mode() -> None:
    for launcher in DESKTOP_LAUNCHERS:
        text = launcher.read_text(encoding="utf-8")
        assert "VulnoraIQ Desktop Mode" in text
        assert "scripts/desktop_launch.py" in text or "scripts\\desktop_launch.py" in text
        assert "scan-reports" in text
        assert "launch-vulnoraiq-docker-lab" in text
        assert "docker compose build" not in text
        assert "bootstrap_launch.py" not in text


def test_desktop_launcher_prepares_agent_lab_project_folders() -> None:
    launcher = (ROOT / "scripts" / "desktop_launch.py").read_text(encoding="utf-8")

    assert "agent_root / \"projects\"" in launcher
    assert "mounted_projects_root = ROOT / \"projects\"" in launcher
    assert "VULNORAIQ_PROJECTS_ROOT" in launcher
    assert "Agent Lab mapped project folder" in launcher


def test_docker_lab_launchers_keep_full_compose_flow() -> None:
    for launcher in DOCKER_LAB_LAUNCHERS:
        text = launcher.read_text(encoding="utf-8")
        assert "Advanced Docker Lab" in text
        assert "docker info" in text
        assert "docker compose build" in text
        assert "docker compose up -d" in text
        assert "docker compose ps" in text
        assert "vulnoraiq-web" in text
        assert "127.0.0.1:8787" in text
        assert "bootstrap_launch.py" not in text


def test_bootstrap_remains_available_for_python_docker_lab_flow() -> None:
    bootstrap = (ROOT / "scripts" / "bootstrap_launch.py").read_text(encoding="utf-8")

    assert "docker" in bootstrap
    assert "compose" in bootstrap
    assert "docker-compose.yml" in bootstrap
    assert "http://127.0.0.1:8787" in bootstrap
    assert "webbrowser.open" in bootstrap
    assert "docker compose logs vulnoraiq-web" in bootstrap


def test_run_mode_guide_documents_launcher_flow() -> None:
    plan = (ROOT / "docs" / "guides" / "desktop-mode.md").read_text(encoding="utf-8")

    assert "Desktop Mode" in plan
    assert "Docker Lab Mode" in plan
    assert "./scan-reports/" in plan
    assert "./agent-lab/projects/" in plan
