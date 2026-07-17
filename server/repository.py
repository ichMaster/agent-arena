from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from server.models import MatchModel, MoveLogModel, ChatLogModel, MatchStatus

class ArenaRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_match(self) -> MatchModel:
        match = MatchModel(status=MatchStatus.PENDING)
        self.session.add(match)
        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def get_match(self, match_id: str) -> Optional[MatchModel]:
        stmt = select(MatchModel).where(MatchModel.id == match_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def log_move(self, match_id: str, player_id: str, move_payload: dict) -> MoveLogModel:
        move = MoveLogModel(match_id=match_id, player_id=player_id, move_payload=move_payload)
        self.session.add(move)
        await self.session.commit()
        await self.session.refresh(move)
        return move

    async def get_moves(self, match_id: str) -> List[MoveLogModel]:
        stmt = select(MoveLogModel).where(MoveLogModel.match_id == match_id).order_by(MoveLogModel.timestamp)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def log_chat(self, match_id: str, sender: str, message: str) -> ChatLogModel:
        chat = ChatLogModel(match_id=match_id, sender=sender, message=message)
        self.session.add(chat)
        await self.session.commit()
        await self.session.refresh(chat)
        return chat

    async def get_chat(self, match_id: str) -> List[ChatLogModel]:
        stmt = select(ChatLogModel).where(ChatLogModel.match_id == match_id).order_by(ChatLogModel.timestamp)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
