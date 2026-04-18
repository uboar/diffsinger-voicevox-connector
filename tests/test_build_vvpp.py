"""VVPP 生成スクリプトのテスト。"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import build_vvpp


def test_detect_os_label_includes_mac_arch(monkeypatch) -> None:
    monkeypatch.setattr(build_vvpp.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(build_vvpp.platform, "machine", lambda: "arm64")

    assert build_vvpp._detect_os_label() == "macos-arm64"


def test_exe_path_accepts_arch_specific_windows_label() -> None:
    assert build_vvpp._exe_path("windows-x64").name == "DiffSingerConnector.exe"


def test_stage_payload_writes_voicevox_installable_manifest(tmp_path: Path) -> None:
    exe = tmp_path / "DiffSingerConnector.exe"
    exe.write_bytes(b"dummy executable")
    stage = tmp_path / "stage"

    build_vvpp._stage_payload(stage, exe, "9.8.7")

    root_manifest = json.loads((stage / "engine_manifest.json").read_text(encoding="utf-8"))
    resources_manifest = json.loads(
        (stage / "resources" / "engine_manifest.json").read_text(encoding="utf-8")
    )

    for manifest in (root_manifest, resources_manifest):
        assert manifest["name"] == "DiffSinger Connector"
        assert manifest["uuid"] == "9e4cf7d0-7a6e-4e5c-9f1d-2b3a5d6e7f80"
        assert manifest["command"] == "DiffSingerConnector.exe"
        assert manifest["port"] == build_vvpp.DEFAULT_VVPP_PORT
        assert manifest["version"] == "9.8.7"
        assert "supported_vvlib_manifest_version" not in manifest
        assert manifest["supported_features"]["sing"]["value"] is True

    assert (stage / "DiffSingerConnector.exe").is_file()
    assert (stage / "models" / "README.txt").is_file()
    assert (stage / "resources" / "icon.png").is_file()
    assert (stage / "resources" / "terms.md").is_file()
