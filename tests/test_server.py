import uuid

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.main import app

client = TestClient(app)


def _join(match_id: str, player_name: str = "Ada") -> str:
    response = client.post("/api/v1/lobby/join", json={"match_id": match_id, "player_name": player_name})
    return response.json()["token"]


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_match_returns_valid_uuid() -> None:
    response = client.post("/api/v1/lobby/match")
    assert response.status_code == 200
    body = response.json()
    assert "match_id" in body
    assert uuid.UUID(body["match_id"]).version == 4


def test_join_match_returns_token() -> None:
    response = client.post(
        "/api/v1/lobby/join", json={"match_id": str(uuid.uuid4()), "player_name": "Ada"}
    )
    assert response.status_code == 200
    assert "token" in response.json()


def test_join_match_rejects_missing_fields() -> None:
    response = client.post("/api/v1/lobby/join", json={"match_id": str(uuid.uuid4())})
    assert response.status_code == 422


def test_ws_connect_with_valid_token_is_accepted() -> None:
    match_id = str(uuid.uuid4())
    token = _join(match_id)
    with client.websocket_connect(f"/ws/match/{match_id}?token={token}") as websocket:
        assert websocket is not None


def test_ws_connect_without_token_is_closed() -> None:
    match_id = str(uuid.uuid4())
    try:
        with client.websocket_connect(f"/ws/match/{match_id}"):
            raise AssertionError("connection should have been closed before accept")
    except WebSocketDisconnect as exc:
        assert exc.code == 4001


def test_ws_connect_with_invalid_token_is_closed() -> None:
    match_id = str(uuid.uuid4())
    try:
        with client.websocket_connect(f"/ws/match/{match_id}?token=not-a-real-token"):
            raise AssertionError("connection should have been closed before accept")
    except WebSocketDisconnect as exc:
        assert exc.code == 4001


def test_ws_connect_with_token_for_different_match_is_closed() -> None:
    joined_match_id = str(uuid.uuid4())
    other_match_id = str(uuid.uuid4())
    token = _join(joined_match_id)
    try:
        with client.websocket_connect(f"/ws/match/{other_match_id}?token={token}"):
            raise AssertionError("connection should have been closed before accept")
    except WebSocketDisconnect as exc:
        assert exc.code == 4001
