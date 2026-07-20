"""Thin seat/turn helpers over the Repository (architecture.md §2, §5.2).

``server/match.py`` holds **no in-memory seat state** — each helper opens a session and delegates to
the Repository's §5.2 seat methods. The seat rule itself lives in the Repository (v01.02); this is
just the service-layer entry point the REST/WS flows call. The session maker is injected (not a
module global) so callers bind it to the same DB as the running app.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.repository import Repository


async def assign_symbol(
    session_maker: async_sessionmaker[AsyncSession], match_id: str, token: str
) -> str | None:
    """Assign (or return the existing) seat for ``token`` per §5.2 — a write-through wrapper."""
    async with session_maker() as session:
        return await Repository(session).assign_symbol(match_id, token)


async def release_seat(
    session_maker: async_sessionmaker[AsyncSession], match_id: str, token: str
) -> None:
    """Free ``token``'s seat so a reconnect can reclaim it."""
    async with session_maker() as session:
        await Repository(session).release_seat(match_id, token)
