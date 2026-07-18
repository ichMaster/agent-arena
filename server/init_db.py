import asyncio
from server.database import Base, engine, async_session_maker
from server.repository import ArenaRepository
from server.models import MatchStatus

async def main():
    print("[*] Initializing Database Schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
    print("[+] Database Schema Created Successfully!")
    
    print("[*] Inserting Dummy Records...")
    async with async_session_maker() as session:
        repo = ArenaRepository(session)
        
        # 1. Create a match
        match = await repo.create_match()
        print(f"    -> Created Match ID: {match.id}")
        
        # 2. Update status to COMPLETED
        await repo.update_match_status(match.id, MatchStatus.COMPLETED)
        print("    -> Updated match status to COMPLETED")
        
        # 3. Log a move
        move = await repo.log_move(match.id, "X", {"cell": 0})
        print(f"    -> Logged move ID: {move.id}")
        
        # 4. Log a chat
        chat = await repo.log_chat(match.id, "System", "Welcome to Agent Arena Tic-Tac-Toe!")
        print(f"    -> Logged chat ID: {chat.id}")
        
        # Verification select
        fetched_match = await repo.get_match(match.id)
        fetched_moves = await repo.get_moves(match.id)
        fetched_chats = await repo.get_chats(match.id)
        
        print("\n[+] Verification Results:")
        print(f"    Match Status: {fetched_match.status}")
        print(f"    Moves logged: {len(fetched_moves)}")
        print(f"    Chats logged: {len(fetched_chats)}")

if __name__ == "__main__":
    asyncio.run(main())
