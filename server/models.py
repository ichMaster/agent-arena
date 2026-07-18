import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import relationship
from server.database import Base

class MatchStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"

class MatchModel(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True, index=True)
    status = Column(Enum(MatchStatus), default=MatchStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    moves = relationship("MoveLogModel", back_populates="match", cascade="all, delete-orphan")
    chats = relationship("ChatLogModel", back_populates="match", cascade="all, delete-orphan")

class MoveLogModel(Base):
    __tablename__ = "move_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False)
    player_id = Column(String, nullable=False)
    move_payload = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    match = relationship("MatchModel", back_populates="moves")

class ChatLogModel(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False)
    sender = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    match = relationship("MatchModel", back_populates="chats")
