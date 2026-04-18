"""model_loader のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

from diffsinger_engine import model_loader  # noqa: E402


def _make_singer_dir(
    base: Path,
    name: str,
    *,
    with_character: bool = False,
    missing: tuple[str, ...] = (),
    vocoder: str = "vocoder.onnx",
) -> Path:
    folder = base / name
    folder.mkdir()
    files = {
        (
            "dsconfig.yaml"
        ): f"phonemes: phonemes.txt\nacoustic: acoustic.onnx\nhop_size: 512\nvocoder: {vocoder}\n",
        "acoustic.onnx": "",
        "vocoder.onnx": "",
        "phonemes.txt": "a\ni\nu\ne\no\nrest\n",
    }
    for filename, content in files.items():
        if filename in missing:
            continue
        (folder / filename).write_text(content, encoding="utf-8")

    if with_character:
        (folder / "character.yaml").write_text(
            "name: テスト歌手\nuuid: 11111111-2222-3333-4444-555555555555\n",
            encoding="utf-8",
        )
    return folder


def test_load_singers_basic(tmp_path: Path) -> None:
    _make_singer_dir(tmp_path, "alpha")
    _make_singer_dir(tmp_path, "beta", with_character=True)

    singers = model_loader.load_singers(tmp_path)
    assert len(singers) == 2

    by_folder = {s.folder.name: s for s in singers}
    assert by_folder["alpha"].name == "alpha"
    # 決定論的 UUID
    assert by_folder["alpha"].uuid
    assert by_folder["beta"].name == "テスト歌手"
    assert by_folder["beta"].uuid == "11111111-2222-3333-4444-555555555555"


def test_load_singers_assigns_sequential_style_ids(tmp_path: Path) -> None:
    _make_singer_dir(tmp_path, "a_singer")
    _make_singer_dir(tmp_path, "b_singer")
    _make_singer_dir(tmp_path, "c_singer")

    singers = model_loader.load_singers(tmp_path)
    style_ids = sorted(s.style_id for s in singers)
    assert style_ids == [0, 1, 2]


def test_load_singers_skips_invalid_folders(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _make_singer_dir(tmp_path, "ok")
    _make_singer_dir(tmp_path, "missing_acoustic", missing=("acoustic.onnx",))
    _make_singer_dir(tmp_path, "missing_dsconfig", missing=("dsconfig.yaml",))

    with caplog.at_level("WARNING"):
        singers = model_loader.load_singers(tmp_path)

    names = {s.folder.name for s in singers}
    assert names == {"ok"}
    # warning が複数出ているはず
    assert any("missing_acoustic" in rec.message or "missing_acoustic" in rec.getMessage()
               for rec in caplog.records)


def test_load_singers_returns_empty_for_nonexistent_dir(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    nonexistent = tmp_path / "no_such"
    with caplog.at_level("WARNING"):
        singers = model_loader.load_singers(nonexistent)
    assert singers == []


def test_load_singers_deterministic_uuid_across_calls(tmp_path: Path) -> None:
    _make_singer_dir(tmp_path, "kasumi")
    first = model_loader.load_singers(tmp_path)[0].uuid
    second = model_loader.load_singers(tmp_path)[0].uuid
    assert first == second


def test_loaded_singer_includes_dsconfig_dict(tmp_path: Path) -> None:
    _make_singer_dir(tmp_path, "alpha")
    [singer] = model_loader.load_singers(tmp_path)
    assert isinstance(singer.dsconfig, dict)
    assert singer.dsconfig.get("hop_size") == 512


def test_icon_and_portrait_optional(tmp_path: Path) -> None:
    folder = _make_singer_dir(tmp_path, "with_icon")
    (folder / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    [singer] = model_loader.load_singers(tmp_path)
    assert singer.icon_path is not None
    assert singer.icon_path.name == "icon.png"
    assert singer.portrait_path is None


def test_load_singers_resolves_shared_vocoder_dir(tmp_path: Path) -> None:
    _make_singer_dir(tmp_path, "alpha", missing=("vocoder.onnx",), vocoder="nsf_hifigan")
    shared = tmp_path / "vocoders"
    shared.mkdir()
    (shared / "nsf_hifigan.onnx").write_bytes(b"fake")
    (shared / "vocoder.yaml").write_text(
        "sample_rate: 44100\nhop_size: 512\n",
        encoding="utf-8",
    )

    [singer] = model_loader.load_singers(tmp_path)
    assert singer.vocoder_path == shared / "nsf_hifigan.onnx"
    assert singer.vocoder_config["sample_rate"] == 44100


def test_load_singers_extracts_vocoder_from_oudep(tmp_path: Path) -> None:
    import zipfile

    _make_singer_dir(tmp_path, "alpha", missing=("vocoder.onnx",), vocoder="nsf_hifigan")
    shared = tmp_path / "vocoders"
    shared.mkdir()

    archive_path = shared / "nsf_hifigan.oudep"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("vocoder.yaml", "model: nsf_hifigan.onnx\nsample_rate: 44100\n")
        archive.writestr("nsf_hifigan.onnx", b"fake-onnx")

    singers = model_loader.load_singers(tmp_path)
    [singer] = singers
    assert singer.vocoder_path.is_file()
    assert singer.vocoder_path.name == "nsf_hifigan.onnx"
    assert singer.vocoder_config["sample_rate"] == 44100


def test_load_singers_ignores_shared_directories(tmp_path: Path) -> None:
    _make_singer_dir(tmp_path, "alpha")
    (tmp_path / "vocoders").mkdir()
    (tmp_path / ".cache").mkdir()

    singers = model_loader.load_singers(tmp_path)
    assert [s.folder.name for s in singers] == ["alpha"]
