"""The four ORM tables (architecture.md §5.1). Reached only through the Repository — never ad-hoc SQL.

`matches` (one row per match), `participants` (seat identity — UNIQUE(match_id, symbol)), `moves`
(the ordered move log, source of truth), `chat_messages` (non-authoritative chat). The `move` payload
is stored opaquely (the game module owns interpretation).
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Match(Base):
    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(primary_key=True)
    game_type: Mapped[str] = mapped_column(default="tictactoe")
    status: Mapped[str] = mapped_column(default="active")  # "active" | "finished"
    result: Mapped[str | None] = mapped_column(default=None)  # "X" | "O" | "draw" | None
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Participant(Base):
    __tablename__ = "participants"
    # Seat identity is keyed by token, never name; at most one X and one O per match (§5.2).
    __table_args__ = (UniqueConstraint("match_id", "symbol", name="uq_match_symbol"),)

    token: Mapped[str] = mapped_column(primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.match_id"))
    player_name: Mapped[str]
    symbol: Mapped[str | None] = mapped_column(default=None)  # "X" | "O" | None (unseated/observer)
    is_spectator: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Move(Base):
    __tablename__ = "moves"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.match_id"))
    player_symbol: Mapped[str]
    move: Mapped[Any] = mapped_column(JSON)  # opaque payload — the store never parses it
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.match_id"))
    sender: Mapped[str]
    message: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
