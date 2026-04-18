"""ローカル起動確認用のスモークテスト。

models/ が空でも確認できるメタ API を対象にする。
必要なら --keep-running でサーバーを立てたままにできる。
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
PYTHON_BIN = ROOT_DIR / ".venv" / "bin" / "python"
DEFAULT_PORT = 50122


def _python_command() -> list[str]:
    if PYTHON_BIN.is_file():
        return [str(PYTHON_BIN)]
    return [sys.executable]


def _request_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=5) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def _wait_for_server(base_url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            version = _request_json(f"{base_url}/version")
            if isinstance(version, str) and version:
                return
        except Exception as exc:  # pragma: no cover - retry path
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"サーバー起動待ちに失敗しました: {last_error}")


def _read_startup_output(process: subprocess.Popen[str]) -> str:
    if process.stdout is None:
        return ""
    try:
        return process.stdout.read().strip()
    except Exception:
        return ""


def main() -> int:
    port = int(os.environ.get("DIFFSINGER_SMOKE_PORT", DEFAULT_PORT))
    keep_running = "--keep-running" in sys.argv[1:]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{ROOT_DIR / 'src'}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(ROOT_DIR / "src")
    )

    command = [
        *_python_command(),
        "-m",
        "diffsinger_engine",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--models",
        str(ROOT_DIR / "models"),
    ]

    process = subprocess.Popen(
        command,
        cwd=ROOT_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"

    try:
        _wait_for_server(base_url)
        version = _request_json(f"{base_url}/version")
        manifest = _request_json(f"{base_url}/engine_manifest")
        health = _request_json(f"{base_url}/health")
        singers = _request_json(f"{base_url}/singers")

        print("Smoke test passed")
        print(f"  version: {version}")
        print(f"  manifest name: {manifest['name']}")
        print(f"  health: {health['status']} (loaded_singers={health['loaded_singers']})")
        print(f"  singers: {len(singers)}")

        if keep_running:
            print(f"Server is still running at {base_url}")
            print("Press Ctrl+C to stop it.")
            process.wait()
        return 0
    except KeyboardInterrupt:
        return 130
    except urllib.error.URLError as exc:
        print(f"HTTP 確認に失敗しました: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        if process.poll() is not None:
            startup_output = _read_startup_output(process)
            if startup_output:
                print(startup_output, file=sys.stderr)
        return 1
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
