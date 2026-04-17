"""PyInstaller を用いてスタンドアロン実行ファイルを生成するスクリプト.

使い方:
    python scripts/build_exe.py [--clean]

出力:
    Windows: dist/DiffSingerConnector.exe
    macOS:   dist/DiffSingerConnector
"""

from __future__ import annotations

import argparse
import importlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
RESOURCES_DIR = REPO_ROOT / "resources"
ENTRYPOINT = SRC_DIR / "diffsinger_engine" / "__main__.py"
APP_NAME = "DiffSingerConnector"


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_configure_stdio()


def _data_sep() -> str:
    """PyInstaller の --add-data 区切り文字 (Windows: ; / その他: :)."""
    return ";" if platform.system() == "Windows" else ":"


def _resolve_pyopenjtalk_dict() -> Path | None:
    """pyopenjtalk が同梱する OpenJTalk 辞書ディレクトリを返す.

    インストール環境にしか存在しないため、見つからなくても警告で済ませる。
    """
    try:
        pyopenjtalk = importlib.import_module("pyopenjtalk")
    except ImportError:
        print("[warn] pyopenjtalk が見つかりません。辞書同梱をスキップします。", file=sys.stderr)
        return None

    candidate_attrs = ["OPEN_JTALK_DICT_DIR", "DEFAULT_DICT_DIR"]
    for attr in candidate_attrs:
        value = getattr(pyopenjtalk, attr, None)
        if value:
            path = Path(os.fsdecode(value))
            if path.exists():
                return path

    pkg_dir = Path(pyopenjtalk.__file__).resolve().parent
    for name in ("open_jtalk_dic_utf_8-1.11", "dictionary"):
        candidate = pkg_dir / name
        if candidate.exists():
            return candidate

    print("[warn] pyopenjtalk 辞書ディレクトリを特定できませんでした。", file=sys.stderr)
    return None


def _build_command(clean: bool) -> list[str]:
    sep = _data_sep()
    cmd: list[str] = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--name",
        APP_NAME,
        "--paths",
        str(SRC_DIR),
        "--add-data",
        f"{RESOURCES_DIR}{sep}resources",
        "--collect-submodules",
        "diffsinger_engine",
        "--collect-data",
        "pyopenjtalk",
    ]
    if clean:
        cmd.append("--clean")

    dict_dir = _resolve_pyopenjtalk_dict()
    if dict_dir is not None:
        cmd.extend(["--add-data", f"{dict_dir}{sep}pyopenjtalk/{dict_dir.name}"])

    cmd.append(str(ENTRYPOINT))
    return cmd


def _ensure_pyinstaller() -> None:
    try:
        importlib.import_module("PyInstaller")
    except ImportError as exc:
        raise SystemExit(
            "PyInstaller が見つかりません。`pip install -e .[build]` を実行してください。"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="PyInstaller でスタンドアロン実行ファイルを生成")
    parser.add_argument("--clean", action="store_true", help="PyInstaller の --clean を有効化")
    parser.add_argument(
        "--keep-build",
        action="store_true",
        help="一時ビルド用 build/ ディレクトリを残す",
    )
    args = parser.parse_args()

    _ensure_pyinstaller()

    if not ENTRYPOINT.exists():
        raise SystemExit(f"エントリーポイントが見つかりません: {ENTRYPOINT}")

    os.chdir(REPO_ROOT)

    cmd = _build_command(clean=args.clean)
    print("[info] PyInstaller を実行します:")
    print("       " + " ".join(cmd))
    subprocess.run(cmd, check=True)

    if not args.keep_build:
        build_dir = REPO_ROOT / "build"
        if build_dir.exists():
            shutil.rmtree(build_dir, ignore_errors=True)

    suffix = ".exe" if platform.system() == "Windows" else ""
    artifact = REPO_ROOT / "dist" / f"{APP_NAME}{suffix}"
    if not artifact.exists():
        raise SystemExit(f"ビルド成果物が見つかりません: {artifact}")

    print()
    print("============================================================")
    print(f" ビルド成功: {artifact}")
    print("============================================================")
    print(" 動作確認:")
    if platform.system() == "Windows":
        print(f"   {artifact} --port 50122")
    else:
        print(f"   {artifact} --port 50122")
    print("   別ターミナルで:")
    print("   curl http://127.0.0.1:50122/version")
    print("============================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
