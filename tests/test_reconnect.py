"""Resilience-verification tests for v05.01 (roadmap §v05.01, architecture §9-§10). Real TestClient
WS connections against a throwaway DB; no LLM, no paid call.

Most resilience behavior shipped in v01.04 (seat release + shielded finally). This file closes the
two gaps found in reconciliation: same-token reconnect-reclaim coverage, and the malformed-JSON
production fix from this same issue.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/reconnect.db")
    app = create_app(db_engine=engine, session_maker=create_session_maker(engine))
    with TestClient(app) as c:
        yield c


def _create_match(client: TestClient) -> str:
    return str(client.post("/api/v1/lobby/match").json()["match_id"])


def _join(client: TestClient, match_id: str, name: str) -> str:
    return str(
        client.post("/api/v1/lobby/join", json={"match_id": match_id, "player_name": name}).json()[
            "token"
        ]
    )


def test_same_token_reconnect_reclaims_seat(client: TestClient) -> None:
    match_id = _create_match(client)
    token_a = _join(client, match_id, "Alice")
    with client.websocket_connect(f"/ws/match/{match_id}?token={token_a}") as ws:
        assert ws.receive_json()["payload"]["symbol"] == "X"
    # dropped -> the shielded finally released the seat.
    with client.websocket_connect(f"/ws/match/{match_id}?token={token_a}") as ws2:
        assert ws2.receive_json()["payload"]["symbol"] == "X"  # same token reclaims the same seat


def test_drop_then_reconnect_leaves_both_seats_usable(client: TestClient) -> None:
    match_id = _create_match(client)
    token_a = _join(client, match_id, "Alice")
    with client.websocket_connect(f"/ws/match/{match_id}?token={token_a}") as ws:
        ws.receive_json()  # X
    with client.websocket_connect(f"/ws/match/{match_id}?token={token_a}") as ws2:
        assert ws2.receive_json()["payload"]["symbol"] == "X"  # A reclaims X
        token_b = _join(client, match_id, "Bob")
        with client.websocket_connect(f"/ws/match/{match_id}?token={token_b}") as ws3:
            assert ws3.receive_json()["payload"]["symbol"] == "O"  # exactly one seat left, none leaked


def test_malformed_json_keeps_connection(client: TestClient) -> None:
    match_id = _create_match(client)
    token = _join(client, match_id, "Alice")
    with client.websocket_connect(f"/ws/match/{match_id}?token={token}") as ws:
        ws.receive_json()  # joined
        ws.send_text("not json at all {{{")
        assert ws.receive_json() == {"event": "error", "payload": {"detail": "malformed message"}}
        # still usable afterward
        ws.send_json({"action": "chat", "payload": {"message": "still here"}})
        assert ws.receive_json()["event"] == "chat_message"


def test_non_object_json_keeps_connection(client: TestClient) -> None:
    match_id = _create_match(client)
    token = _join(client, match_id, "Alice")
    with client.websocket_connect(f"/ws/match/{match_id}?token={token}") as ws:
        ws.receive_json()
        ws.send_text("[1, 2, 3]")  # valid JSON, not an object
        assert ws.receive_json() == {"event": "error", "payload": {"detail": "malformed message"}}
