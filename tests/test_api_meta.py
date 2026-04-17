"""/version, /engine_manifest, /supported_devices, /health のテスト。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from diffsinger_engine import __version__
from diffsinger_engine.app import create_app


@pytest.fixture()
def client(settings):  # type: ignore[no-untyped-def]
    app = create_app(settings)
    # lifespan を明示的に走らせるために TestClient コンテキストで初期化。
    with TestClient(app) as c:
        yield c


def test_version_returns_string(client: TestClient) -> None:
    res = client.get("/version")
    assert res.status_code == 200
    assert res.json() == __version__


def test_engine_manifest_schema(client: TestClient) -> None:
    res = client.get("/engine_manifest")
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["name"] == "DiffSinger Connector"
    assert data["brand_name"] == "DiffSinger"
    assert data["frame_rate"] == 93.75
    assert data["default_sampling_rate"] == 24000

    # icon は base64 PNG 化されているはず (元のファイル名ではない)
    assert isinstance(data["icon"], str)
    assert not data["icon"].endswith(".png")

    # terms_of_service はファイル名でなく Markdown 本文
    assert "DiffSinger Connector" in data["terms_of_service"]

    # update_infos / dependency_licenses は配列にデシリアライズ済み
    assert isinstance(data["update_infos"], list)
    assert len(data["update_infos"]) >= 1
    assert isinstance(data["dependency_licenses"], list)

    # supported_features の sing が True
    assert data["supported_features"]["sing"]["value"] is True


def test_supported_devices(client: TestClient) -> None:
    res = client.get("/supported_devices")
    assert res.status_code == 200
    data = res.json()
    assert data["cpu"] is True
    assert isinstance(data["cuda"], bool)
    assert isinstance(data["dml"], bool)


def test_health_no_models(client: TestClient) -> None:
    """models_dir が空なら status=no_models, loaded_singers=0。"""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "no_models"
    assert data["loaded_singers"] == 0
