from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models import ChatLogModel, MatchModel, MatchStatus, MoveLogModel


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_match(self, match_id: str, status: MatchStatus = MatchStatus.PENDING) -> MatchModel:
        match = MatchModel(id=match_id, status=status)
        self._session.add(match)
        await self._session.commit()
        return match

    async def get_match(self, match_id: str) -> MatchModel | None:
        return await self._session.get(MatchModel, match_id)

    async def log_move(self, match_id: str, player_id: str, move_payload: dict[str, Any]) -> MoveLogModel:
        move = MoveLogModel(match_id=match_id, player_id=player_id, move_payload=move_payload)
        self._session.add(move)
        await self._session.commit()
        return move

    async def get_move_logs(self, match_id: str) -> list[MoveLogModel]:
        result = await self._session.execute(
            select(MoveLogModel).where(MoveLogModel.match_id == match_id).order_by(MoveLogModel.id)
        )
        return list(result.scalars().all())

    async def log_chat(self, match_id: str, sender: str, message: str) -> ChatLogModel:
        chat = ChatLogModel(match_id=match_id, sender=sender, message=message)
        self._session.add(chat)
        await self._session.commit()
        return chat

    async def get_chat_logs(self, match_id: str) -> list[ChatLogModel]:
        result = await self._session.execute(
            select(ChatLogModel).where(ChatLogModel.match_id == match_id).order_by(ChatLogModel.id)
        )
        return list(result.scalars().all())
