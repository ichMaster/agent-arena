import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, NullPool

# Default DB URL, check environment variable for tests to override
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///arena.db")

engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
    connect_args={"timeout": 30},
    echo=False
)

# Enforce foreign key constraints in SQLite
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()
