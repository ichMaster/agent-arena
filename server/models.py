"""SQLAlchemy ORM models — the four persistence tables (architecture.md §5.1).

All durable state: ``matches``, ``participants`` (seats), ``moves`` (the ordered move log — the
source of truth for board state), and ``chat_messages`` (non-authoritative flavor). Reached only
through the Repository (server/repository.py). Seats are unique per ``(match_id, symbol)`` so a
match holds at most one X and one O.
"""

import datetime as dt
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from server.database import Base


class Match(Base):
    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(String, primary_key=True)
    game_type: Mapped[str] = mapped_column(String, nullable=False, default="tictactoe")
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")  # active | finished
    result: Mapped[str | None] = mapped_column(String, nullable=True)  # X | O | draw | None
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class Participant(Base):
    __tablename__ = "participants"
    # At most one X and one O per match — the seat-uniqueness guard (§5.1/§5.2).
    __table_args__ = (UniqueConstraint("match_id", "symbol", name="uq_participant_match_symbol"),)

    token: Mapped[str] = mapped_column(String, primary_key=True)  # the participant_id (§6.3)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.match_id"), nullable=False)
    player_name: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)  # X | O | None (unseated)
    is_spectator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class Move(Base):
    __tablename__ = "moves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.match_id"), nullable=False)
    player_symbol: Mapped[str] = mapped_column(String, nullable=False)
    # Opaque move payload, stored as JSON so its type round-trips untouched (the store never
    # interprets it — the game module owns interpretation). For TicTacToe this is an int cell 0-8.
    move: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.match_id"), nullable=False)
    sender: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
