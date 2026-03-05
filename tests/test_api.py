"""
API 测试
"""

import pytest
from fastapi.testclient import TestClient

from agent2any.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_sessions_empty(client):
    response = client.get("/api/v1/sessions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_session_not_found(client):
    response = client.get("/api/v1/sessions/non-existent")
    assert response.status_code == 404


def test_delete_session_not_found(client):
    response = client.delete("/api/v1/sessions/non-existent")
    assert response.status_code == 404
