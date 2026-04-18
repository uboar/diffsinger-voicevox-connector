from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_main_module_can_run_as_script_entrypoint() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    entrypoint = repo_root / "src" / "diffsinger_engine" / "__main__.py"

    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    src_dir = str(repo_root / "src")
    env["PYTHONPATH"] = src_dir if not pythonpath else os.pathsep.join([src_dir, pythonpath])

    completed = subprocess.run(
        [sys.executable, str(entrypoint), "--version"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "0.1.0" in completed.stdout
