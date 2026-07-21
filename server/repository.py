"""Repository — the single access seam for durable state (architecture.md §5.1).

Every read or write to matches, seats, moves, or chat goes through this class; no handler issues
ad-hoc SQL of its own. One `Repository` wraps one `AsyncSession` supplied by the caller.
"""

from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models import ChatMessage, Match, Move, Participant

_SYMBOLS: Final = ("X", "O")


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

    async def assign_symbol(self, match_id: str, token: str) -> str | None:
        """The §5.2 seat rule, write-through over the `participants` row."""
        participant = await self._session.get(Participant, token)
        if participant is None or participant.is_spectator:
            return None
        if participant.symbol is not None:
            return participant.symbol  # idempotent reconnect
        taken = set(
            (
                await self._session.execute(
                    select(Participant.symbol).where(
                        Participant.match_id == match_id, Participant.symbol.is_not(None)
                    )
                )
            )
            .scalars()
            .all()
        )
        free = next((symbol for symbol in _SYMBOLS if symbol not in taken), None)
        if free is None:
            return None  # both seats already taken
        participant.symbol = free
        await self._session.commit()
        return free

    async def release_seat(self, match_id: str, token: str) -> None:
        """Clear the participant's symbol so a later connection can reclaim it."""
        participant = await self._session.get(Participant, token)
        if participant is not None:
            participant.symbol = None
            await self._session.commit()
