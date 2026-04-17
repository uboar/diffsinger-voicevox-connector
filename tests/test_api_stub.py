"""talk 型スタブエンドポイントのテスト。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from diffsinger_engine.app import create_app


@pytest.fixture()
def client(settings):  # type: ignore[no-untyped-def]
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def test_speakers_empty(client: TestClient) -> None:
    res = client.get("/speakers")
    assert res.status_code == 200
    assert res.json() == []


def test_speaker_info_404(client: TestClient) -> None:
    res = client.get("/speaker_info")
    assert res.status_code == 404
    assert "talk" in res.json()["detail"]


def test_audio_query_501(client: TestClient) -> None:
    res = client.post("/audio_query")
    assert res.status_code == 501


def test_synthesis_501(client: TestClient) -> None:
    res = client.post("/synthesis")
    assert res.status_code == 501
