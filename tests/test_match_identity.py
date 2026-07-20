"""End-to-end seat-by-token identity (architecture §5.2) — real join tokens through `match.py`.

Drives the lobby over ``TestClient`` (writing to a temp-file DB), then assigns seats through the
`match.py` helpers on a **separate** engine bound to the same file (so the async seat calls run on
the test's own event loop, not TestClient's portal loop). Data flows via the committed SQLite file —
exactly the REST-writes-then-WS-reads path of production. No LLM, no paid call.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.database import create_engine, create_session_maker
from server.main import create_app
from server.match import assign_symbol, release_seat

DB_NAME = "seat.db"


@pytest.fixture
def lobby(tmp_path: Path) -> Iterator[tuple[TestClient, str]]:
    db_url = f"sqlite+aiosqlite:///{tmp_path}/{DB_NAME}"
    engine = create_engine(db_url)
    maker = create_session_maker(engine)
    app = create_app(db_engine=engine, session_maker=maker)
    with TestClient(app) as client:
        yield client, db_url


def _create_match(client: TestClient) -> str:
    return str(client.post("/api/v1/lobby/match").json()["match_id"])


def _join(client: TestClient, match_id: str, name: str, spectator: bool = False) -> str:
    body = {"match_id": match_id, "player_name": name, "spectator": spectator}
    return str(client.post("/api/v1/lobby/join", json=body).json()["token"])


async def _assign(db_url: str, match_id: str, token: str) -> str | None:
    """Assign a seat on a fresh engine bound to the same file (own event loop)."""
    engine = create_engine(db_url)
    try:
        return await assign_symbol(create_session_maker(engine), match_id, token)
    finally:
        await engine.dispose()


async def test_two_join_tokens_get_x_and_o(lobby: tuple[TestClient, str]) -> None:
    client, db_url = lobby
    match_id = _create_match(client)
    token_a = _join(client, match_id, "Alice")
    token_b = _join(client, match_id, "Bob")
    assert await _assign(db_url, match_id, token_a) == "X"
    assert await _assign(db_url, match_id, token_b) == "O"


async def test_third_player_gets_no_seat(lobby: tuple[TestClient, str]) -> None:
    client, db_url = lobby
    match_id = _create_match(client)
    tokens = [_join(client, match_id, name) for name in ("A", "B", "C")]
    seats = [await _assign(db_url, match_id, token) for token in tokens]
    assert seats == ["X", "O", None]


async def test_spectator_join_is_never_seated(lobby: tuple[TestClient, str]) -> None:
    client, db_url = lobby
    match_id = _create_match(client)
    observer = _join(client, match_id, "Watcher", spectator=True)
    assert await _assign(db_url, match_id, observer) is None


async def test_same_display_name_gets_distinct_seats(lobby: tuple[TestClient, str]) -> None:
    client, db_url = lobby
    match_id = _create_match(client)
    # Both named "Human" — keyed by token, they must NOT collide onto one seat.
    token_a = _join(client, match_id, "Human")
    token_b = _join(client, match_id, "Human")
    assert token_a != token_b
    assert await _assign(db_url, match_id, token_a) == "X"
    assert await _assign(db_url, match_id, token_b) == "O"


async def test_release_seat_frees_it_for_reclaim(lobby: tuple[TestClient, str]) -> None:
    client, db_url = lobby
    match_id = _create_match(client)
    token_a = _join(client, match_id, "A")
    token_b = _join(client, match_id, "B")
    assert await _assign(db_url, match_id, token_a) == "X"
    assert await _assign(db_url, match_id, token_b) == "O"

    engine = create_engine(db_url)
    try:
        await release_seat(create_session_maker(engine), match_id, token_a)  # free X
    finally:
        await engine.dispose()

    token_c = _join(client, match_id, "C")
    assert await _assign(db_url, match_id, token_c) == "X"  # reclaims the freed seat
