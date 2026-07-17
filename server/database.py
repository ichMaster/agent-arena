import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# Use in-memory DB for tests if specified, otherwise a file-based one
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///arena.db")

engine = create_async_engine(DATABASE_URL, echo=False)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()
