from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from server.models import MatchModel, MatchStatus, MoveLogModel, ChatLogModel

class Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert_match(self, match_id: str) -> MatchModel:
        match = MatchModel(id=match_id, status=MatchStatus.PENDING)
        self.session.add(match)
        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def fetch_match(self, match_id: str) -> MatchModel | None:
        stmt = select(MatchModel).where(MatchModel.id == match_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def log_move(self, match_id: str, player_id: str, move_payload: dict) -> MoveLogModel:
        move = MoveLogModel(match_id=match_id, player_id=player_id, move_payload=move_payload)
        self.session.add(move)
        await self.session.commit()
        await self.session.refresh(move)
        return move

    async def fetch_move_logs(self, match_id: str) -> list[MoveLogModel]:
        stmt = select(MoveLogModel).where(MoveLogModel.match_id == match_id).order_by(MoveLogModel.timestamp)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def log_chat_message(self, match_id: str, sender: str, message: str) -> ChatLogModel:
        chat = ChatLogModel(match_id=match_id, sender=sender, message=message)
        self.session.add(chat)
        await self.session.commit()
        await self.session.refresh(chat)
        return chat

    async def fetch_chat_logs(self, match_id: str) -> list[ChatLogModel]:
        stmt = select(ChatLogModel).where(ChatLogModel.match_id == match_id).order_by(ChatLogModel.timestamp)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
