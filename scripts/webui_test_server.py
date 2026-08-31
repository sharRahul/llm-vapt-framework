from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    output_root = Path(os.getenv("VULNORAIQ_WEB_OUTPUT_ROOT", "reports/output/webui-playwright"))
    job_store = Path(os.getenv("VULNORAIQ_JOB_STORE_PATH", str(output_root / "jobs.db")))
    output_root.mkdir(parents=True, exist_ok=True)
    job_store.parent.mkdir(parents=True, exist_ok=True)

    from webui.server import main as serve_web_ui  # noqa: PLC0415

    serve_web_ui()


if __name__ == "__main__":
    main()
