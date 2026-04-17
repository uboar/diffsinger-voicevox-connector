"""日本語ログ設定。コンソール出力 + ./logs/connector.log にローテート保存。"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(logs_dir: Path, level: str = "INFO") -> None:
    """ロガー初期化。複数回呼ばれてもハンドラを重複登録しない。"""
    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level.upper())

    if any(getattr(h, "_diffsinger_marker", False) for h in root.handlers):
        return

    formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console._diffsinger_marker = True  # type: ignore[attr-defined]
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "connector.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler._diffsinger_marker = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    # uvicorn のアクセスログを統一書式で出す
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(noisy).handlers = []
        logging.getLogger(noisy).propagate = True
