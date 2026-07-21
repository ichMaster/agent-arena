"""Repository — the single access seam for all durable state (architecture.md §5.1).

Every read/write of the four tables goes through here; no ad-hoc SQL escapes into handlers. One
Repository wraps one `AsyncSession`. Live game state is never stored as mutable fields — it is
reconstructed by replaying the move log (ARENA-OPUS-OPUS-007). The `move` payload is opaque: the store
persists it as-is and the game module owns interpretation.
"""

from typing import Any

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from server.models import ChatMessage, Match, Move, Participant


class Repository:
    """Async CRUD over one session. Reads return ORM objects usable after commit."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_match(self, match_id: str, game_type: str = "tictactoe") -> None:
        self._session.add(Match(match_id=match_id, game_type=game_type))
        await self._session.commit()

    async def get_match(self, match_id: str) -> Match | None:
        return await self._session.get(Match, match_id)

    async def get_participant(self, token: str) -> Participant | None:
        return await self._session.get(Participant, token)

    async def add_participant(
        self, token: str, match_id: str, name: str, is_spectator: bool = False
    ) -> None:
        self._session.add(
            Participant(
                token=token, match_id=match_id, player_name=name, is_spectator=is_spectator
            )
        )
        await self._session.commit()

    async def log_move(self, match_id: str, symbol: str, move: Any) -> None:
        self._session.add(Move(match_id=match_id, player_symbol=symbol, move=move))
        await self._session.commit()

    async def log_chat(self, match_id: str, sender: str, message: str) -> None:
        self._session.add(ChatMessage(match_id=match_id, sender=sender, message=message))
        await self._session.commit()

    async def _moves_in_order(self, match_id: str) -> list[Move]:
        result = await self._session.execute(
            select(Move).where(Move.match_id == match_id).order_by(Move.id)
        )
        return list(result.scalars().all())
