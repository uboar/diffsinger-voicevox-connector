"""歌唱合成エンドポイント (/sing_frame_*, /frame_synthesis)。"""

from __future__ import annotations

import logging

import numpy as np
from fastapi import APIRouter, Body, Query, Request, Response

from ..inference.frame_query import VOICEVOX_FRAME_RATE, build_frame_query
from ..inference.postprocess import to_wav_bytes
from ..inference.score_converter import score_to_ds_input
from ..runtime_state import get_or_load_models, get_singer
from ..schemas import FrameAudioQuery, Score

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sing"])


def _build_query_for_singer(request: Request, score: Score) -> FrameAudioQuery:
    settings = request.app.state.settings
    ds_input = score_to_ds_input(score, frame_rate=VOICEVOX_FRAME_RATE)
    return build_frame_query(
        score=score,
        ds_input=ds_input,
        output_sr=int(settings.final_sampling_rate),
    )


# ──────────────────────── /sing_frame_audio_query ────────────────────────

@router.post("/sing_frame_audio_query", response_model=FrameAudioQuery)
def sing_frame_audio_query(
    request: Request,
    score: Score = Body(...),
    speaker: int = Query(..., description="GET /singers の style id"),
) -> FrameAudioQuery:
    get_singer(request, speaker)  # 存在検証
    return _build_query_for_singer(request, score)


# ──────────────────────── /sing_frame_f0 ────────────────────────

class _ScoreAndQuery(dict):
    """Body 用の最小スキーマ (Pydantic で受け取るため dict ベース)。"""


@router.post("/sing_frame_f0", response_model=list[float])
def sing_frame_f0(
    request: Request,
    payload: dict = Body(..., description="{score: Score, frame_audio_query: FrameAudioQuery}"),
    speaker: int = Query(...),
) -> list[float]:
    get_singer(request, speaker)
    score = Score.model_validate(payload["score"])
    return _build_query_for_singer(request, score).f0


# ──────────────────────── /sing_frame_volume ────────────────────────

@router.post("/sing_frame_volume", response_model=list[float])
def sing_frame_volume(
    request: Request,
    payload: dict = Body(..., description="{score: Score, frame_audio_query: FrameAudioQuery}"),
    speaker: int = Query(...),
) -> list[float]:
    get_singer(request, speaker)
    score = Score.model_validate(payload["score"])
    return _build_query_for_singer(request, score).volume


# ──────────────────────── /frame_synthesis ────────────────────────

@router.post(
    "/frame_synthesis",
    responses={200: {"content": {"audio/wav": {}}}},
    response_class=Response,
)
def frame_synthesis(
    request: Request,
    query: FrameAudioQuery = Body(...),
    speaker: int = Query(...),
) -> Response:
    singer = get_singer(request, speaker)
    acoustic, vocoder = get_or_load_models(request.app, singer)

    # FrameAudioQuery → acoustic 入力。実モデルが要求する具体的な
    # テンソル名は dsconfig 依存のため、ここでは最小セットを渡す。
    f0 = np.asarray(query.f0, dtype=np.float32)
    volume = np.asarray(query.volume, dtype=np.float32)
    tokens = np.asarray(
        [_phoneme_to_token_id(p.phoneme) for p in query.phonemes],
        dtype=np.int64,
    )[None, :]
    durations = np.asarray(
        [p.frame_length for p in query.phonemes], dtype=np.int64
    )[None, :]

    features = {
        "tokens": tokens,
        "durations": durations,
        "f0": f0[None, :],
        "volume": volume[None, :],
    }

    mel = acoustic.run(features)
    waveform = vocoder.run(mel, f0)

    wav_bytes = to_wav_bytes(
        waveform,
        src_sr=int(getattr(vocoder, "sample_rate", 44100)),
        target_sr=int(query.outputSamplingRate),
    )
    return Response(content=wav_bytes, media_type="audio/wav")


def _phoneme_to_token_id(phoneme: str) -> int:
    """phoneme 文字列を簡易的に整数 ID に変換 (実モデル使用時はモデル付属辞書で再マップ)。"""
    return abs(hash(phoneme)) % 10000
