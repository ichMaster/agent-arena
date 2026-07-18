import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MatchStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class MatchModel(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    status: Mapped[MatchStatus] = mapped_column(Enum(MatchStatus), default=MatchStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    moves: Mapped[list["MoveLogModel"]] = relationship(back_populates="match", cascade="all, delete-orphan")
    chat_messages: Mapped[list["ChatLogModel"]] = relationship(back_populates="match", cascade="all, delete-orphan")


class MoveLogModel(Base):
    __tablename__ = "move_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"))
    player_id: Mapped[str] = mapped_column()
    move_payload: Mapped[dict] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    match: Mapped["MatchModel"] = relationship(back_populates="moves")


class ChatLogModel(Base):
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"))
    sender: Mapped[str] = mapped_column()
    message: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    match: Mapped["MatchModel"] = relationship(back_populates="chat_messages")
