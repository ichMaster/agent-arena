"""Repository — the single access seam for all durable state (architecture.md §5.1).

Every DB read/write goes through here; no ad-hoc SQL lives in handlers. One ``Repository`` wraps one
``AsyncSession``. Reads return ORM objects that stay usable after commit (``expire_on_commit=False``,
§10). The opaque ``move`` payload is persisted as-is — the store never interprets it.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from server.models import ChatMessage, Match, Move, Participant


class Repository:
    """All durable reads/writes for one match session, over a single ``AsyncSession``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_match(self, match_id: str, game_type: str = "tictactoe") -> None:
        self._session.add(Match(match_id=match_id, game_type=game_type))
        await self._session.commit()

    async def get_match(self, match_id: str) -> Match | None:
        return await self._session.get(Match, match_id)

    async def add_participant(
        self, token: str, match_id: str, name: str, is_spectator: bool
    ) -> None:
        self._session.add(
            Participant(
                token=token,
                match_id=match_id,
                player_name=name,
                is_spectator=is_spectator,
            )
        )
        await self._session.commit()

    async def log_move(self, match_id: str, symbol: str, move: Any) -> None:
        self._session.add(Move(match_id=match_id, player_symbol=symbol, move=move))
        await self._session.commit()

    async def log_chat(self, match_id: str, sender: str, message: str) -> None:
        self._session.add(ChatMessage(match_id=match_id, sender=sender, message=message))
        await self._session.commit()
