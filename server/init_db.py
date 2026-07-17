import asyncio
from server.database import engine, Base, async_session_maker
from server.repository import ArenaRepository

async def main():
    print("Initializing Database Schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    print("Inserting Dummy Data...")
    async with async_session_maker() as session:
        repo = ArenaRepository(session)
        match = await repo.create_match()
        print(f"Created Match: {match.id}")
        
        move = await repo.log_move(match.id, "Alice", {"x": 1, "y": 2})
        print(f"Logged Move: {move.id}")
        
        chat = await repo.log_chat(match.id, "Bob", "Hello!")
        print(f"Logged Chat: {chat.id}")

    print("Success! Database populated.")

if __name__ == "__main__":
    asyncio.run(main())
