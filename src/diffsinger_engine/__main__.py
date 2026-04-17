"""エントリーポイント: `python -m diffsinger_engine`"""

from __future__ import annotations

from pathlib import Path

import click
import uvicorn

from . import __version__
from .settings import reload_settings


@click.command(help="DiffSinger × VOICEVOX Connector を起動します")
@click.option("--host", default=None, help="バインドホスト (既定: 127.0.0.1)")
@click.option("--port", type=int, default=None, help="HTTP ポート (既定: 50122)")
@click.option(
    "--models",
    "models_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="DiffSinger モデルディレクトリ (既定: ./models)",
)
@click.option(
    "--final-sampling-rate",
    type=int,
    default=None,
    help="frame_synthesis の既定出力サンプリングレート (既定: 44100)",
)
@click.option("--gpu", "--use_gpu", is_flag=True, default=False, help="CUDAExecutionProvider を試行")
@click.option("--log-level", default=None, help="DEBUG/INFO/WARNING/ERROR")
@click.version_option(__version__)
def main(
    host: str | None,
    port: int | None,
    models_dir: Path | None,
    final_sampling_rate: int | None,
    gpu: bool,
    log_level: str | None,
) -> None:
    overrides: dict[str, object] = {}
    if host is not None:
        overrides["host"] = host
    if port is not None:
        overrides["port"] = port
    if models_dir is not None:
        overrides["models_dir"] = models_dir
    if final_sampling_rate is not None:
        overrides["final_sampling_rate"] = final_sampling_rate
    if gpu:
        overrides["use_gpu"] = True
    if log_level:
        overrides["log_level"] = log_level

    settings = reload_settings(**overrides)

    # app は遅延 import (CLI ヘルプを軽くするため)
    from .app import create_app

    app = create_app(settings)

    click.echo(
        f"DiffSinger Connector v{__version__} を起動します "
        f"(http://{settings.host}:{settings.port})"
    )
    click.echo(f"  モデルディレクトリ: {settings.models_dir.resolve()}")
    click.echo(f"  ログ: {settings.logs_dir.resolve()}/connector.log")

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_config=None,  # logging_config.py で統一済み
    )


if __name__ == "__main__":
    main()
