"""FastAPI app factory。

ルーターは routers/ 配下で実装する（タスク #3）。
ここでは骨格と、起動時のモデルスキャン・ヘルスチェックだけを定義する。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .logging_config import setup_logging
from .settings import Settings, get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    setup_logging(settings.logs_dir, settings.log_level)

    # model_loader は推論モジュール (タスク #2) で実装される。
    # 未実装段階でも起動できるよう、import をここに閉じ込めて遅延ロードする。
    try:
        from .model_loader import load_singers

        singers = load_singers(
            settings.models_dir,
            vocoder_cache_dir=settings.vocoder_cache_dir,
        )
        app.state.singers = singers
        app.state.user_dict_store = {}
        app.state.initialized_speaker_ids = set()
        logger.info("DiffSinger 歌手モデルを %d 件読み込みました", len(singers))
        if not singers:
            logger.warning(
                "models/ に有効な DiffSinger モデルがありません。"
                "docs/MODEL_SETUP.md を参照してください。"
            )
    except ImportError:
        logger.warning("model_loader が未実装のため、歌手リストは空で起動します")
        app.state.singers = []
        app.state.user_dict_store = {}
        app.state.initialized_speaker_ids = set()

    yield
    logger.info("DiffSinger Connector を停止しました")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title="DiffSinger × VOICEVOX Connector",
        description=(
            "VOICEVOX Engine 互換 HTTP サーバー。"
            "歌唱合成リクエストを openvpi DiffSinger ONNX モデルで処理します。"
        ),
        version=__version__,
        lifespan=_lifespan,
    )
    app.state.settings = settings

    # VOICEVOX Editor (Electron) からの XHR は同一ホスト扱いになるが、
    # ブラウザ確認用途も考えて localhost からは緩めに許可する。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ルーター登録 (実体はタスク #3)。未実装でも起動だけはできるようにする。
    try:
        from .routers import compat, meta, sing, singers, tts_stub

        app.include_router(meta.router)
        app.include_router(singers.router)
        app.include_router(sing.router)
        app.include_router(compat.router)
        app.include_router(tts_stub.router)
    except ImportError as e:
        logger.warning("ルーター未実装のためスキップ: %s", e)

    return app
