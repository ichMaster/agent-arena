"""Repository — the single access seam for all durable state (architecture.md §5.1).

Every read/write of the four tables goes through here; no ad-hoc SQL escapes into handlers. One
Repository wraps one `AsyncSession`. Live game state is never stored as mutable fields — it is
reconstructed by replaying the move log (ARENA-OPUS-OPUS-007). The `move` payload is opaque: the store
persists it as-is and the game module owns interpretation.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from games.interface import GameInterface
from games.tictactoe import TicTacToe
from server.models import ChatMessage, Match, Move, Participant

_SYMBOLS: tuple[str, ...] = ("X", "O")


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

    async def assign_symbol(self, match_id: str, token: str) -> str | None:
        """Seat rule (§5.2), write-through and idempotent. Returns the seat, or None if the token
        can't hold one (unknown/spectator/match-full).

        Race-safe: two connections claiming the last free symbol both pass the read, but the
        `UNIQUE(match_id, symbol)` constraint fails one commit — that caller rolls back and retries,
        re-reading the now-updated taken set (and getting the other seat, or None if full). Bounded
        by the number of symbols + 1 so it always terminates.
        """
        for _ in range(len(_SYMBOLS) + 1):
            participant = await self._session.get(Participant, token)
            if participant is None or participant.is_spectator:
                return None
            if participant.symbol is not None:
                return participant.symbol  # idempotent reconnect
            taken = await self._taken_symbols(match_id)
            free = [s for s in _SYMBOLS if s not in taken]
            if not free:
                return None  # match full
            participant.symbol = free[0]
            try:
                await self._session.commit()
                return free[0]
            except IntegrityError:
                await self._session.rollback()  # lost the race for free[0] — retry re-reads taken
        return None

    async def finish_match(self, match_id: str, result: str) -> None:
        """Mark a match finished with its result (§5.4 step 4)."""
        match = await self._session.get(Match, match_id)
        if match is not None:
            match.status = "finished"
            match.result = result
            await self._session.commit()

    async def release_seat(self, match_id: str, token: str) -> None:
        """Clear a participant's symbol so a reconnect can reclaim it (§5.2, §10 cleanup)."""
        participant = await self._session.get(Participant, token)
        if participant is not None and participant.symbol is not None:
            participant.symbol = None
            await self._session.commit()

    async def _taken_symbols(self, match_id: str) -> set[str]:
        result = await self._session.execute(
            select(Participant.symbol).where(
                Participant.match_id == match_id, Participant.symbol.is_not(None)
            )
        )
        return {s for s in result.scalars().all() if s is not None}

    async def reconstruct_game(self, match_id: str) -> GameInterface:
        """Rebuild live state by replaying the ordered move log through a fresh TicTacToe (§5.1).

        The server holds no board state of its own — the move log is the source of truth, so board /
        whose-turn / result all survive a restart and a reconnect.
        """
        game = TicTacToe()
        for move_row in await self._moves_in_order(match_id):
            game.apply_move(move_row.player_symbol, move_row.move)
        return game

    async def current_turn(self, match_id: str) -> str | None:
        """Whose turn, derived from move-count parity — None once the game is over (§5.1)."""
        game = await self.reconstruct_game(match_id)
        if game.is_game_over() is not None:
            return None
        move_count = len(await self._moves_in_order(match_id))
        return _SYMBOLS[move_count % len(_SYMBOLS)]  # X on an even count, O on odd

    async def _moves_in_order(self, match_id: str) -> list[Move]:
        result = await self._session.execute(
            select(Move).where(Move.match_id == match_id).order_by(Move.id)
        )
        return list(result.scalars().all())
