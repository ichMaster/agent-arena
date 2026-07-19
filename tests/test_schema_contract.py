"""Contract test — the four persistence table shapes (roadmap §v01.02 Tests, architecture §5.1).

Pins table names, columns, primary keys, the ``match_id`` foreign keys, and the seat-uniqueness
constraint. Pure metadata introspection — no database, no LLM. A schema change updates §5.1 and
this test together.
"""

from sqlalchemy import UniqueConstraint

from server import models  # noqa: F401  (registers the ORM tables on Base.metadata)
from server.database import Base

EXPECTED_TABLES = {"matches", "participants", "moves", "chat_messages"}

EXPECTED_COLUMNS = {
    "matches": {"match_id", "game_type", "status", "result", "created_at"},
    "participants": {"token", "match_id", "player_name", "symbol", "is_spectator", "created_at"},
    "moves": {"id", "match_id", "player_symbol", "move", "created_at"},
    "chat_messages": {"id", "match_id", "sender", "message", "created_at"},
}

EXPECTED_PRIMARY_KEYS = {
    "matches": {"match_id"},
    "participants": {"token"},
    "moves": {"id"},
    "chat_messages": {"id"},
}


def test_table_names() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_columns_per_table() -> None:
    for table, columns in EXPECTED_COLUMNS.items():
        assert set(Base.metadata.tables[table].columns.keys()) == columns


def test_primary_keys() -> None:
    for table, pk in EXPECTED_PRIMARY_KEYS.items():
        actual = {col.name for col in Base.metadata.tables[table].primary_key.columns}
        assert actual == pk


def test_foreign_keys_reference_matches() -> None:
    for table in ("participants", "moves", "chat_messages"):
        fks = Base.metadata.tables[table].foreign_keys
        assert any(
            fk.column.table.name == "matches" and fk.column.name == "match_id" for fk in fks
        ), f"{table}.match_id must reference matches.match_id"


def test_seat_uniqueness_constraint() -> None:
    participants = Base.metadata.tables["participants"]
    unique_constraints = [c for c in participants.constraints if isinstance(c, UniqueConstraint)]
    assert any(
        {col.name for col in c.columns} == {"match_id", "symbol"} for c in unique_constraints
    ), "participants must carry UNIQUE(match_id, symbol)"
