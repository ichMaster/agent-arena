"""Thin seat/turn service helpers over the Repository (architecture.md §2, §5.2).

There is no long-lived in-memory Match object — each call opens its own session and delegates to the
Repository's §5.2 rule. The seat rule itself is never re-implemented here.
"""

from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from server.repository import Repository


async def assign_symbol(
    session_maker: async_sessionmaker[Any], match_id: str, token: str
) -> str | None:
    """Open a session and delegate to Repository.assign_symbol (the §5.2 rule)."""
    async with session_maker() as session:
        return await Repository(session).assign_symbol(match_id, token)


async def release_seat(
    session_maker: async_sessionmaker[Any], match_id: str, token: str
) -> None:
    """Open a session and delegate to Repository.release_seat."""
    async with session_maker() as session:
        await Repository(session).release_seat(match_id, token)
