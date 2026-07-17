import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Text, JSON
from server.database import Base

class MatchStatus(enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

class MatchModel(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True, default=generate_uuid)
    status = Column(Enum(MatchStatus), default=MatchStatus.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

class MoveLogModel(Base):
    __tablename__ = "move_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    match_id = Column(String, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    player_id = Column(String, nullable=False)
    move_payload = Column(JSON, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False)

class ChatLogModel(Base):
    __tablename__ = "chat_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    match_id = Column(String, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    sender = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False)
