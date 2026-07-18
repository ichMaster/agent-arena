import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import relationship
from server.database import Base

class MatchStatus(enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"

class MatchModel(Base):
    __tablename__ = "matches"
    
    id = Column(String, primary_key=True)
    status = Column(Enum(MatchStatus), nullable=False, default=MatchStatus.PENDING)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Cascade deletes to moves and chats
    moves = relationship("MoveLogModel", back_populates="match", cascade="all, delete-orphan")
    chats = relationship("ChatLogModel", back_populates="match", cascade="all, delete-orphan")

class MoveLogModel(Base):
    __tablename__ = "move_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    player_id = Column(String, nullable=False)
    move_payload = Column(JSON, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    match = relationship("MatchModel", back_populates="moves")

class ChatLogModel(Base):
    __tablename__ = "chat_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    sender = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    match = relationship("MatchModel", back_populates="chats")
