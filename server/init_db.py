import asyncio
import uuid

from server.database import async_session_maker, init_models
from server.repository import Repository


async def main() -> None:
    await init_models()
    async with async_session_maker() as session:
        repository = Repository(session)
        match_id = str(uuid.uuid4())
        await repository.create_match(match_id)
        await repository.log_chat(match_id, sender="system", message="Match initialized.")
        await repository.log_move(match_id, player_id="X", move_payload={"cell": 0})

        matches = await repository.get_match(match_id)
        chats = await repository.get_chat_logs(match_id)
        moves = await repository.get_move_logs(match_id)

    print("Database schema initialized at arena.db")
    print(f"Inserted match: {matches.id if matches else 'MISSING'}")
    print(f"Chat logs recorded: {len(chats)}")
    print(f"Move logs recorded: {len(moves)}")


if __name__ == "__main__":
    asyncio.run(main())
