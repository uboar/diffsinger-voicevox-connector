"""ローカル起動確認用のスモークテスト。

既定ではメタ API の疎通だけを確認する。
`--synthesize` を付けると、最初に見つかった歌手で実際に 1 音だけ歌わせて WAV 生成まで検証する。
OpenUtau 形式モデルが `vocoder: nsf_hifigan` を要求する場合は
`--download-openutau-vocoder` で共有 vocoder を `models/vocoders/` に自動配置できる。
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
PYTHON_BIN = ROOT_DIR / ".venv" / "bin" / "python"
DEFAULT_PORT = 50122
DEFAULT_OUTPUT_WAV = ROOT_DIR / "logs" / "smoke_test_song.wav"
OPENUTAU_NSF_HIFIGAN_URL = (
    "https://github.com/xunmengshe/OpenUtau/releases/download/0.0.0.0/nsf_hifigan.oudep"
)


def _python_command() -> list[str]:
    if PYTHON_BIN.is_file():
        return [str(PYTHON_BIN)]
    return [sys.executable]


def _request_json(url: str, *, method: str = "GET", body: object | None = None) -> object:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = response.read()
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            raise RuntimeError(f"JSON を期待しましたが {content_type!r} が返りました: {url}")
    return json.loads(payload.decode("utf-8"))


def _request_bytes(url: str, *, method: str = "GET", body: object | None = None) -> bytes:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


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


def _ensure_openutau_vocoder() -> Path:
    vocoder_dir = ROOT_DIR / "models" / "vocoders"
    vocoder_dir.mkdir(parents=True, exist_ok=True)

    archive_path = vocoder_dir / "nsf_hifigan.oudep"
    onnx_path = vocoder_dir / "nsf_hifigan.onnx"
    if onnx_path.is_file():
        return onnx_path

    if not archive_path.is_file():
        print(f"Downloading shared vocoder: {OPENUTAU_NSF_HIFIGAN_URL}")
        urllib.request.urlretrieve(OPENUTAU_NSF_HIFIGAN_URL, archive_path)

    with zipfile.ZipFile(archive_path) as archive:
        member_name = "nsf_hifigan.onnx"
        with archive.open(member_name) as src, onnx_path.open("wb") as dst:
            dst.write(src.read())

        if "vocoder.yaml" in archive.namelist():
            config_path = vocoder_dir / "vocoder.yaml"
            with archive.open("vocoder.yaml") as src, config_path.open("wb") as dst:
                dst.write(src.read())

    return onnx_path


def _make_score(lyric: str, midi: int) -> dict[str, object]:
    return {
        "notes": [
            {"key": None, "frame_length": 8, "lyric": ""},
            {"key": midi, "frame_length": 32, "lyric": lyric},
            {"key": None, "frame_length": 8, "lyric": ""},
        ]
    }


def _run_real_synthesis(
    base_url: str,
    *,
    lyric: str,
    midi: int,
    output_wav: Path,
) -> tuple[str, int, Path]:
    singers = _request_json(f"{base_url}/singers")
    if not isinstance(singers, list) or not singers:
        raise RuntimeError("歌手が見つかりませんでした。models/ と vocoder 配置を確認してください。")

    singer = singers[0]
    style_id = singer["styles"][0]["id"]
    singer_name = singer["name"]

    score = _make_score(lyric=lyric, midi=midi)
    query = _request_json(
        f"{base_url}/sing_frame_audio_query?speaker={style_id}",
        method="POST",
        body=score,
    )
    wav = _request_bytes(
        f"{base_url}/frame_synthesis?speaker={style_id}",
        method="POST",
        body=query,
    )

    output_wav.parent.mkdir(parents=True, exist_ok=True)
    output_wav.write_bytes(wav)
    return str(singer_name), int(style_id), output_wav


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DiffSinger Connector のローカルスモークテスト")
    parser.add_argument("--port", type=int, default=int(os.environ.get("DIFFSINGER_SMOKE_PORT", DEFAULT_PORT)))
    parser.add_argument("--keep-running", action="store_true")
    parser.add_argument("--synthesize", action="store_true", help="実際に WAV 生成まで確認する")
    parser.add_argument(
        "--download-openutau-vocoder",
        action="store_true",
        help="models/vocoders/ に nsf_hifigan を自動配置する",
    )
    parser.add_argument("--lyric", default="あ", help="歌唱確認に使う 1 モーラ歌詞")
    parser.add_argument("--midi", type=int, default=60, help="歌唱確認に使う MIDI ノート番号")
    parser.add_argument("--output-wav", type=Path, default=DEFAULT_OUTPUT_WAV)
    return parser.parse_args(argv)


def main() -> int:
    args = _parse_args(sys.argv[1:])
    port = int(args.port)

    if args.download_openutau_vocoder:
        onnx_path = _ensure_openutau_vocoder()
        print(f"Shared vocoder ready: {onnx_path}")

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

        if args.synthesize:
            singer_name, style_id, output_wav = _run_real_synthesis(
                base_url,
                lyric=args.lyric,
                midi=args.midi,
                output_wav=args.output_wav,
            )
            print(f"  synthesized singer: {singer_name} (style_id={style_id})")
            print(f"  wav: {output_wav}")

        if args.keep_running:
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
