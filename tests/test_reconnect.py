"""Reconnect resilience — the one coverage gap for v05.01 (ARENA-OPUS-034).

The resilience *code* is already shipped (release-on-disconnect under asyncio.shield, broadcast
pruning, malformed-JSON handling, 4001 token close, model-error fallback — see the v05.01 issues doc).
These tests close the missing case: a participant that drops and reconnects on the SAME token reclaims
a seat, and the two-seat invariant holds across a drop/reconnect cycle (no seat leaked). No LLM.
"""

import time
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


def _join(client: TestClient, match_id: str, name: str) -> str:
    return str(client.post("/api/v1/lobby/join",
                           json={"match_id": match_id, "player_name": name}).json()["token"])


def test_same_token_reconnect_reclaims_seat(client: TestClient) -> None:
    """A drops mid-match, then reconnects on the same token and holds a seat again."""
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    a_token = _join(client, match_id, "Alice")

    with client.websocket_connect(f"/ws/match/{match_id}?token={a_token}") as wa1:
        assert wa1.receive_json()["payload"]["symbol"] == "X"
    # A's socket dropped; the shielded cleanup frees the seat. A reconnects on the same token:
    # assign_symbol is idempotent-or-reassigns, so A reclaims X either way.
    with client.websocket_connect(f"/ws/match/{match_id}?token={a_token}") as wa2:
        assert wa2.receive_json()["payload"]["symbol"] == "X"


def test_drop_then_reconnect_leaves_both_seats_usable(client: TestClient) -> None:
    """After an A drop + same-token reconnect, B still takes the other seat — exactly two, none leaked."""
    match_id = client.post("/api/v1/lobby/match").json()["match_id"]
    a_token = _join(client, match_id, "Alice")
    b_token = _join(client, match_id, "Bob")

    with client.websocket_connect(f"/ws/match/{match_id}?token={a_token}") as wa1:
        assert wa1.receive_json()["payload"]["symbol"] == "X"

    # Retry the reclaim+join sequence so the shielded release from the old socket has settled: once it
    # has, A reclaims X and B gets O — proving no seat was leaked or duplicated across the cycle.
    seats = None
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        with client.websocket_connect(f"/ws/match/{match_id}?token={a_token}") as wa2:
            sym_a = wa2.receive_json()["payload"]["symbol"]
            with client.websocket_connect(f"/ws/match/{match_id}?token={b_token}") as wb:
                sym_b = wb.receive_json()["payload"]["symbol"]
            if {sym_a, sym_b} == {"X", "O"}:
                seats = (sym_a, sym_b)
                break
        time.sleep(0.05)
    assert seats == ("X", "O")  # A reclaimed X, B took O — the two-seat invariant held
