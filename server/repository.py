"""Repository — the single access seam for durable state (architecture.md §5.1).

Every read or write to matches, seats, moves, or chat goes through this class; no handler issues
ad-hoc SQL of its own. One `Repository` wraps one `AsyncSession` supplied by the caller.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from server.models import ChatMessage, Match, Move, Participant


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_match(self, match_id: str, game_type: str = "tictactoe") -> None:
        self._session.add(Match(match_id=match_id, game_type=game_type))
        await self._session.commit()

    async def get_match(self, match_id: str) -> Match | None:
        return await self._session.get(Match, match_id)

    async def add_participant(
        self, token: str, match_id: str, player_name: str, is_spectator: bool = False
    ) -> None:
        self._session.add(
            Participant(
                token=token,
                match_id=match_id,
                player_name=player_name,
                is_spectator=is_spectator,
            )
        )
        await self._session.commit()

    async def log_move(self, match_id: str, symbol: str, move: Any) -> None:
        # `move` is opaque to the store (architecture.md §4.1) -- persisted as-is (the models.py
        # JSON column keeps its real type), never interpreted here.
        self._session.add(Move(match_id=match_id, player_symbol=symbol, move=move))
        await self._session.commit()

    async def log_chat(self, match_id: str, sender: str, message: str) -> None:
        self._session.add(ChatMessage(match_id=match_id, sender=sender, message=message))
        await self._session.commit()
