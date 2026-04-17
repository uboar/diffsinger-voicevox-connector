"""/singers, /sing_frame_audio_query, /frame_synthesis のテスト。

実 ONNX モデルは無いので、AcousticModel / Vocoder をモンキーパッチして
WAV バイナリ生成までの経路だけを検証する。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
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
        icon_path=None,
        portrait_path=None,
        character={},
    )


@pytest.fixture(autouse=True)
def _stub_g2p(monkeypatch):  # type: ignore[no-untyped-def]
    """pyopenjtalk 非導入環境でも回る簡易 G2P スタブ。"""
    from diffsinger_engine.inference import score_converter

    def _fake(text: str) -> list[str]:
        if not text:
            return []
        # 1モーラ = 母音 1 個と仮定したダミー
        return ["a"]

    monkeypatch.setattr(score_converter, "hiragana_to_phonemes", _fake)


@pytest.fixture()
def client(settings, tmp_path):  # type: ignore[no-untyped-def]
    app = create_app(settings)
    with TestClient(app) as c:
        # lifespan で空の singers が入っているので、ダミー 1 件で上書き。
        c.app.state.singers = [_make_dummy_singer(tmp_path / "dummy_singer")]
        yield c


def test_singers_endpoint_returns_one(client: TestClient) -> None:
    res = client.get("/singers")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 1
    singer = data[0]
    assert singer["name"] == "テスト歌手"
    assert singer["speaker_uuid"] == "00000000-0000-0000-0000-000000000001"
    assert len(singer["styles"]) == 1
    assert singer["styles"][0]["type"] == "sing"
    assert singer["styles"][0]["id"] == 0


def test_singer_info_returns_404_for_unknown_uuid(client: TestClient) -> None:
    res = client.get("/singer_info", params={"speaker_uuid": "non-existent"})
    assert res.status_code == 404


def test_singer_info_url_format_rejected(client: TestClient) -> None:
    res = client.get(
        "/singer_info",
        params={
            "speaker_uuid": "00000000-0000-0000-0000-000000000001",
            "resource_format": "url",
        },
    )
    assert res.status_code == 400


def test_sing_frame_audio_query(client: TestClient) -> None:
    # 簡易 Score: 無音 → 「あ」(D4=62) → 無音
    score = {
        "notes": [
            {"key": None, "frame_length": 10, "lyric": ""},
            {"key": 62, "frame_length": 30, "lyric": "あ"},
            {"key": None, "frame_length": 5, "lyric": ""},
        ]
    }
    res = client.post("/sing_frame_audio_query", params={"speaker": 0}, json=score)
    assert res.status_code == 200, res.text
    q = res.json()

    assert isinstance(q["f0"], list)
    assert isinstance(q["volume"], list)
    assert isinstance(q["phonemes"], list)
    assert q["outputSamplingRate"] == 44100
    # F0 / volume の長さは phonemes 合計フレームと一致
    total = sum(p["frame_length"] for p in q["phonemes"])
    assert len(q["f0"]) == total
    assert len(q["volume"]) == total


def test_sing_frame_audio_query_unknown_speaker_404(client: TestClient) -> None:
    res = client.post(
        "/sing_frame_audio_query",
        params={"speaker": 999},
        json={"notes": []},
    )
    assert res.status_code == 404


def test_sing_frame_f0_and_volume(client: TestClient) -> None:
    score = {"notes": [{"key": 60, "frame_length": 20, "lyric": "あ"}]}
    payload = {"score": score, "frame_audio_query": {}}

    res_f0 = client.post("/sing_frame_f0", params={"speaker": 0}, json=payload)
    assert res_f0.status_code == 200
    assert isinstance(res_f0.json(), list)

    res_vol = client.post("/sing_frame_volume", params={"speaker": 0}, json=payload)
    assert res_vol.status_code == 200
    assert isinstance(res_vol.json(), list)


# ──────────────────────── /frame_synthesis (モック) ────────────────────────

class _FakeAcoustic:
    def __init__(self, *_args, **_kwargs) -> None:
        self.onnx_path = None
        self.dsconfig = {}
        self.providers = ["CPUExecutionProvider"]

    def run(self, _features) -> np.ndarray:
        # mel: (1, 80, T) のダミー
        return np.zeros((1, 80, 32), dtype=np.float32)


class _FakeVocoder:
    sample_rate = 44100

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def run(self, _mel, _f0) -> np.ndarray:
        # 0.1 秒ぶんの無音波形 (44100Hz * 0.1)
        return np.zeros(4410, dtype=np.float32)


def test_frame_synthesis_returns_wav(monkeypatch, client: TestClient) -> None:
    # ルーター内で直接 AcousticModel/Vocoder を import せず、
    # runtime_state.get_or_load_models 経由で読んでいるので、その内部で
    # 参照されるシンボルを差し替える。
    from diffsinger_engine.inference import diffsinger_runner, vocoder
    from diffsinger_engine.routers import sing as sing_router

    monkeypatch.setattr(diffsinger_runner, "AcousticModel", _FakeAcoustic)
    monkeypatch.setattr(vocoder, "Vocoder", _FakeVocoder)

    # soundfile/librosa 非導入環境でも回るよう、エンコーダもモック化。
    def _fake_to_wav(_waveform, src_sr, target_sr):  # type: ignore[no-untyped-def]
        # 最小の RIFF/WAVE ヘッダ + 0 フレーム
        return b"RIFF" + b"\x00" * 4 + b"WAVE"

    monkeypatch.setattr(sing_router, "to_wav_bytes", _fake_to_wav)

    # キャッシュをリセット
    client.app.state.acoustic_cache = {}
    client.app.state.vocoder_cache = {}

    query = {
        "f0": [220.0] * 16,
        "volume": [1.0] * 16,
        "phonemes": [
            {"phoneme": "rest", "frame_length": 4},
            {"phoneme": "a", "frame_length": 8},
            {"phoneme": "rest", "frame_length": 4},
        ],
        "volumeScale": 1.0,
        "outputSamplingRate": 44100,
        "outputStereo": False,
    }
    res = client.post("/frame_synthesis", params={"speaker": 0}, json=query)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("audio/wav")
    assert res.content[:4] == b"RIFF"


def test_frame_synthesis_model_load_failure_returns_500(
    monkeypatch, client: TestClient
) -> None:
    """モデルロードが失敗したら日本語の 500 メッセージを返す。"""

    class _Boom:
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("ONNX file missing")

    from diffsinger_engine.inference import diffsinger_runner, vocoder

    monkeypatch.setattr(diffsinger_runner, "AcousticModel", _Boom)
    monkeypatch.setattr(vocoder, "Vocoder", _Boom)
    client.app.state.acoustic_cache = {}
    client.app.state.vocoder_cache = {}

    query = {
        "f0": [220.0] * 4,
        "volume": [1.0] * 4,
        "phonemes": [{"phoneme": "a", "frame_length": 4}],
        "volumeScale": 1.0,
        "outputSamplingRate": 44100,
        "outputStereo": False,
    }
    res = client.post("/frame_synthesis", params={"speaker": 0}, json=query)
    assert res.status_code == 500
    assert "DiffSinger" in res.json()["detail"]
    assert "MODEL_SETUP" in res.json()["detail"]
