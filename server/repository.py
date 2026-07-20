"""Repository — the single access seam for all durable state (architecture.md §5.1).

Every DB read/write goes through here; no ad-hoc SQL lives in handlers. One ``Repository`` wraps one
``AsyncSession``. Reads return ORM objects that stay usable after commit (``expire_on_commit=False``,
§10). The opaque ``move`` payload is persisted as-is — the store never interprets it.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from games.interface import GameInterface
from games.tictactoe import TicTacToe
from server.models import ChatMessage, Match, Move, Participant

_SYMBOLS: tuple[str, str] = ("X", "O")


class Repository:
    """All durable reads/writes for one match session, over a single ``AsyncSession``."""

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

    async def finish_match(self, match_id: str, result: str) -> None:
        """Mark a match finished with its result (``X``/``O``/``draw``)."""
        match = await self._session.get(Match, match_id)
        if match is not None:
            match.status = "finished"
            match.result = result
            await self._session.commit()

    async def assign_symbol(self, match_id: str, token: str) -> str | None:
        """Assign a seat to ``token`` per the §5.2 rule; write-through, keyed by token not name.

        Order: unknown token or spectator -> None; already seated -> that symbol (idempotent
        reconnect); both seats taken -> None; else the first free symbol (X then O), persisted.
        ``UNIQUE(match_id, symbol)`` guards a concurrent double-assign.
        """
        participant = await self._session.get(Participant, token)
        if participant is None or participant.is_spectator:
            return None
        if participant.symbol is not None:
            return participant.symbol  # idempotent reconnect
        taken = set(
            (
                await self._session.execute(
                    select(Participant.symbol).where(
                        Participant.match_id == match_id,
                        Participant.symbol.is_not(None),
                    )
                )
            ).scalars().all()
        )
        for symbol in _SYMBOLS:
            if symbol not in taken:
                participant.symbol = symbol
                await self._session.commit()
                return symbol
        return None  # both seats taken

    async def release_seat(self, match_id: str, token: str) -> None:
        """Clear ``token``'s seat so a reconnect can reclaim the freed symbol."""
        participant = await self._session.get(Participant, token)
        if participant is not None and participant.symbol is not None:
            participant.symbol = None
            await self._session.commit()

    async def reconstruct_game(self, match_id: str) -> GameInterface:
        """Rebuild live state by replaying the ordered move log through a fresh ``TicTacToe``.

        The move log is the source of truth (§5.1); no board snapshot is stored, so no
        serialize/deserialize is added to ``GameInterface``.
        """
        moves = (
            await self._session.execute(
                select(Move).where(Move.match_id == match_id).order_by(Move.id)
            )
        ).scalars().all()
        game: GameInterface = TicTacToe()
        for move in moves:
            game.apply_move(move.player_symbol, move.move)
        return game

    async def current_turn(self, match_id: str) -> str | None:
        """Derive whose turn it is: move-count parity (X on even), ``None`` once the game is over."""
        game = await self.reconstruct_game(match_id)
        if game.is_game_over() is not None:
            return None
        filled = sum(1 for cell in game.get_state()["board"] if cell)
        return _SYMBOLS[filled % 2]
