import asyncio
import uuid
from server.database import engine, Base, async_session
from server.repository import Repository
from server.models import MatchModel, MoveLogModel, ChatLogModel

async def init_db():
    print("Initializing database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database schema created.")

    async with async_session() as session:
        repo = Repository(session)
        
        match_id = str(uuid.uuid4())
        print(f"Creating match {match_id}...")
        match = await repo.insert_match(match_id)
        
        print("Inserting chat message...")
        await repo.log_chat_message(match_id, "System", "Welcome to Agent Arena!")
        
        print("Inserting move log...")
        await repo.log_move(match_id, "player1", {"action": "join"})
        
        print("Fetching match data...")
        fetched_match = await repo.fetch_match(match_id)
        print(f"Match status: {fetched_match.status}")
        
        chats = await repo.fetch_chat_logs(match_id)
        print(f"Chats: {len(chats)}")
        
        moves = await repo.fetch_move_logs(match_id)
        print(f"Moves: {len(moves)}")
        
    print("Database verification successful.")

if __name__ == "__main__":
    asyncio.run(init_db())
