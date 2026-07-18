import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from server.models import MatchModel, MatchStatus, MoveLogModel, ChatLogModel

class ArenaRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def create_match(self) -> MatchModel:
        match_id = str(uuid.uuid4())
        match = MatchModel(id=match_id, status=MatchStatus.PENDING)
        self.session.add(match)
        await self.session.commit()
        await self.session.refresh(match)
        return match
        
    async def get_match(self, match_id: str) -> MatchModel | None:
        result = await self.session.execute(
            select(MatchModel).where(MatchModel.id == match_id)
        )
        return result.scalar_one_or_none()
        
    async def update_match_status(self, match_id: str, status: MatchStatus) -> MatchModel | None:
        match = await self.get_match(match_id)
        if match:
            match.status = status
            self.session.add(match)
            await self.session.commit()
            await self.session.refresh(match)
        return match
        
    async def log_move(self, match_id: str, player_id: str, move_payload: dict) -> MoveLogModel:
        move = MoveLogModel(
            match_id=match_id,
            player_id=player_id,
            move_payload=move_payload
        )
        self.session.add(move)
        await self.session.commit()
        await self.session.refresh(move)
        return move
        
    async def get_moves(self, match_id: str) -> list[MoveLogModel]:
        result = await self.session.execute(
            select(MoveLogModel)
            .where(MoveLogModel.match_id == match_id)
            .order_by(MoveLogModel.timestamp.asc())
        )
        return list(result.scalars().all())
        
    async def log_chat(self, match_id: str, sender: str, message: str) -> ChatLogModel:
        chat = ChatLogModel(
            match_id=match_id,
            sender=sender,
            message=message
        )
        self.session.add(chat)
        await self.session.commit()
        await self.session.refresh(chat)
        return chat
        
    async def get_chats(self, match_id: str) -> list[ChatLogModel]:
        result = await self.session.execute(
            select(ChatLogModel)
            .where(ChatLogModel.match_id == match_id)
            .order_by(ChatLogModel.timestamp.asc())
        )
        return list(result.scalars().all())
