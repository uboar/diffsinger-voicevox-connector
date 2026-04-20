"""VOICEVOX 互換 API のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from diffsinger_engine.app import create_app
from diffsinger_engine.model_loader import LoadedSinger


def _make_dummy_singer(folder: Path, style_id: int = 0) -> LoadedSinger:
    folder.mkdir(parents=True, exist_ok=True)
    return LoadedSinger(
        uuid="00000000-0000-0000-0000-000000000001",
        name="テスト歌手",
        style_id=style_id,
        folder=folder,
        dsconfig={"hop_size": 512, "sample_rate": 44100},
        acoustic_path=folder / "acoustic.onnx",
        vocoder_path=folder / "vocoder.onnx",
        phonemes_path=folder / "phonemes.txt",
        phoneme_to_id={"SP": 0, "a": 1, "rest": 0},
        icon_path=None,
        portrait_path=None,
        character={},
        vocoder_config={"sample_rate": 44100, "hop_size": 512},
    )


@pytest.fixture()
def client(settings, tmp_path):  # type: ignore[no-untyped-def]
    app = create_app(settings)
    with TestClient(app) as c:
        c.app.state.singers = [_make_dummy_singer(tmp_path / "dummy_singer")]
        yield c


def test_user_dict_starts_empty(client: TestClient) -> None:
    res = client.get("/user_dict")
    assert res.status_code == 200
    assert res.json() == {}


def test_user_dict_add_rewrite_delete_roundtrip(client: TestClient) -> None:
    added = client.post(
        "/user_dict_word",
        params={
            "surface": "歌声",
            "pronunciation": "ウタゴエ",
            "accent_type": 3,
            "priority": 7,
        },
    )
    assert added.status_code == 200, added.text
    word_uuid = added.json()

    words = client.get("/user_dict").json()
    assert words[word_uuid]["surface"] == "歌声"
    assert words[word_uuid]["yomi"] == "ウタゴエ"
    assert words[word_uuid]["accent_type"] == 3
    assert words[word_uuid]["priority"] == 7

    rewritten = client.put(
        f"/user_dict_word/{word_uuid}",
        params={
            "surface": "歌ごえ",
            "pronunciation": "ウタゴエ",
            "accent_type": 2,
        },
    )
    assert rewritten.status_code == 204

    words = client.get("/user_dict").json()
    assert words[word_uuid]["surface"] == "歌ごえ"
    assert words[word_uuid]["accent_type"] == 2

    deleted = client.delete(f"/user_dict_word/{word_uuid}")
    assert deleted.status_code == 204
    assert client.get("/user_dict").json() == {}


def test_import_user_dict_honors_override(client: TestClient) -> None:
    imported = {
        "word-1": {
            "surface": "歌",
            "priority": 5,
            "context_id": 1348,
            "part_of_speech": "名詞",
            "part_of_speech_detail_1": "一般",
            "part_of_speech_detail_2": "*",
            "part_of_speech_detail_3": "*",
            "inflectional_type": "*",
            "inflectional_form": "*",
            "stem": "歌",
            "yomi": "ウタ",
            "pronunciation": "ウタ",
            "accent_type": 1,
            "mora_count": 2,
            "accent_associative_rule": "*",
        }
    }
    res = client.post("/import_user_dict", params={"override": True}, json=imported)
    assert res.status_code == 204
    assert client.get("/user_dict").json()["word-1"]["surface"] == "歌"

    res = client.post(
        "/import_user_dict",
        params={"override": False},
        json={"word-1": {**imported["word-1"], "surface": "上書きされない"}},
    )
    assert res.status_code == 204
    assert client.get("/user_dict").json()["word-1"]["surface"] == "歌"


def test_initialize_speaker_roundtrip(monkeypatch, client: TestClient) -> None:
    from diffsinger_engine.routers import compat

    called = []

    def _fake_get_or_load_models(app, singer):  # type: ignore[no-untyped-def]
        called.append((app, singer.style_id))
        return object(), object()

    monkeypatch.setattr(compat, "get_or_load_models", _fake_get_or_load_models)

    res = client.get("/is_initialized_speaker", params={"speaker": 0})
    assert res.status_code == 200
    assert res.json() is False

    init = client.post("/initialize_speaker", params={"speaker": 0})
    assert init.status_code == 204
    assert called == [(client.app, 0)]

    res = client.get("/is_initialized_speaker", params={"speaker": 0})
    assert res.status_code == 200
    assert res.json() is True


def test_initialize_speaker_accepts_voicevox_song_style_id_alias(
    monkeypatch, client: TestClient
) -> None:
    from diffsinger_engine.routers import compat

    called = []

    def _fake_get_or_load_models(app, singer):  # type: ignore[no-untyped-def]
        called.append((app, singer.style_id))
        return object(), object()

    monkeypatch.setattr(compat, "get_or_load_models", _fake_get_or_load_models)

    res = client.get("/is_initialized_speaker", params={"speaker": 6000})
    assert res.status_code == 200
    assert res.json() is False

    init = client.post("/initialize_speaker", params={"speaker": 6000})
    assert init.status_code == 204
    assert called == [(client.app, 0)]

    res = client.get("/is_initialized_speaker", params={"speaker": 6000})
    assert res.status_code == 200
    assert res.json() is True
