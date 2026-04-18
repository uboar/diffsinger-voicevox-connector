"""VVPP パッケージを生成するスクリプト.

dist/DiffSingerConnector(.exe) と resources/ をまとめ、最上位に
engine_manifest.json を持つ zip を作成し拡張子 .vvpp で保存する。

使い方:
    python scripts/build_vvpp.py [--version X.Y.Z] [--os PLATFORM_LABEL]
"""

from __future__ import annotations

import argparse
import importlib
import json
import platform
import shutil
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = REPO_ROOT / "resources"
DIST_DIR = REPO_ROOT / "dist"
APP_NAME = "DiffSingerConnector"
DEFAULT_VVPP_PORT = 50122

REQUIRED_RESOURCES = (
    "engine_manifest.json",
    "terms.md",
    "update_infos.json",
    "dependency_licenses.json",
)


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


def _detect_version() -> str:
    pyproject = REPO_ROOT / "pyproject.toml"
    if pyproject.exists():
        with pyproject.open("rb") as fp:
            data = tomllib.load(fp)
        version = data.get("project", {}).get("version")
        if version:
            return str(version)

    sys.path.insert(0, str(REPO_ROOT / "src"))
    try:
        module = importlib.import_module("diffsinger_engine")
        return getattr(module, "__version__", "0.0.0")
    finally:
        sys.path.pop(0)


def _detect_os_label() -> str:
    name = platform.system().lower()
    machine = platform.machine().lower()
    if name.startswith("win"):
        return "windows"
    if name == "darwin":
        arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
        return f"macos-{arch}"
    if name == "linux":
        return "linux"
    return name or "unknown"


def _exe_path(os_label: str) -> Path:
    suffix = ".exe" if os_label.startswith("windows") else ""
    return DIST_DIR / f"{APP_NAME}{suffix}"


def _ensure_icon(target: Path) -> None:
    """resources/icon.png が無ければ Pillow でプレースホルダを生成して配置."""
    src_icon = RESOURCES_DIR / "icon.png"
    if not src_icon.exists():
        try:
            from PIL import Image
        except ImportError as exc:
            raise SystemExit(
                "icon.png が無く、Pillow も未インストールです。"
                "`pip install Pillow` するか resources/icon.png を配置してください。"
            ) from exc
        img = Image.new("RGBA", (256, 256), (45, 110, 200, 255))
        img.save(src_icon, format="PNG")
        print(f"[info] プレースホルダ icon.png を生成しました: {src_icon}")
    shutil.copy2(src_icon, target / "icon.png")


def _copy_manifest_assets(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_RESOURCES:
        if name == "engine_manifest.json":
            continue
        src = RESOURCES_DIR / name
        if not src.exists():
            raise SystemExit(f"必須リソースが見つかりません: {src}")
        shutil.copy2(src, target / name)

    _ensure_icon(target)


def _load_manifest_template() -> dict[str, object]:
    manifest_path = RESOURCES_DIR / "engine_manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"必須リソースが見つかりません: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"engine_manifest.json の形式が不正です: {manifest_path}")
    return data


def _package_manifest(exe: Path, version: str) -> dict[str, object]:
    manifest = _load_manifest_template()
    manifest["command"] = exe.name
    manifest["port"] = DEFAULT_VVPP_PORT
    manifest["version"] = version
    manifest.pop("supported_vvlib_manifest_version", None)
    _validate_package_manifest(manifest)
    return manifest


def _validate_package_manifest(manifest: dict[str, object]) -> None:
    required = {
        "name": str,
        "uuid": str,
        "command": str,
        "port": int,
        "version": str,
        "supported_features": dict,
    }
    for key, expected_type in required.items():
        value = manifest.get(key)
        if not isinstance(value, expected_type):
            raise SystemExit(
                "engine_manifest.json の VVPP 必須項目が不正です: "
                f"{key}={value!r}"
            )


def _write_manifest(target: Path, manifest: dict[str, object]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _stage_payload(stage: Path, exe: Path, version: str) -> None:
    stage.mkdir(parents=True, exist_ok=True)

    manifest = _package_manifest(exe, version)
    _write_manifest(stage / "engine_manifest.json", manifest)
    _copy_manifest_assets(stage)

    # VOICEVOX はルートの manifest を読む。起動後のエンジンは cwd/resources を読む。
    resources_stage = stage / "resources"
    _write_manifest(resources_stage / "engine_manifest.json", manifest)
    _copy_manifest_assets(resources_stage)

    shutil.copy2(exe, stage / exe.name)

    models_dir = stage / "models"
    models_dir.mkdir(exist_ok=True)
    readme = models_dir / "README.txt"
    readme.write_text(
        "ここに DiffSinger モデルのフォルダを配置してください。\n"
        "詳しくは docs/MODEL_SETUP.md を参照してください。\n",
        encoding="utf-8",
    )


def _zip_stage(stage: Path, output: Path) -> None:
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for entry in sorted(stage.rglob("*")):
            arcname = entry.relative_to(stage).as_posix()
            if entry.is_dir():
                zf.writestr(arcname + "/", "")
            else:
                zf.write(entry, arcname)


def main() -> int:
    parser = argparse.ArgumentParser(description="DiffSinger Connector の VVPP を生成")
    parser.add_argument("--version", default=None, help="バージョン (既定: pyproject.toml から取得)")
    parser.add_argument(
        "--os",
        dest="os_label",
        default=None,
        help="配布ファイル名に使うプラットフォームラベル (既定: 実行中の OS から推定)",
    )
    args = parser.parse_args()

    version = args.version or _detect_version()
    os_label = args.os_label or _detect_os_label()

    exe = _exe_path(os_label)
    if not exe.exists():
        raise SystemExit(
            f"実行ファイルが見つかりません: {exe}\n"
            "先に `python scripts/build_exe.py` を実行してください。"
        )

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    output = DIST_DIR / f"{APP_NAME}-{version}-{os_label}.vvpp"

    with tempfile.TemporaryDirectory(prefix="vvpp-stage-") as tmp:
        stage = Path(tmp) / "vvpp"
        _stage_payload(stage, exe, version)
        _zip_stage(stage, output)

    print()
    print("============================================================")
    print(f" VVPP 生成成功: {output}")
    print("============================================================")
    print(" 動作確認:")
    print("   1. VOICEVOX Editor を起動")
    print("   2. 設定 → エンジン → 追加 → 上記 .vvpp を選択")
    print("   3. ソング画面で 'DiffSinger' 系の歌手が出ることを確認")
    print("============================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
