"""Manual seat / observer client for AgentArena — until the Web UI (v03) exists.

Join a match from the terminal: play a seat (X/O) by typing cell numbers, or watch as an
observer. Pure external client over REST + WS, exactly like an agent or the future UI.

Examples:
  # create a fresh match and take a seat (prints the match id to share)
  python play.py --new --name You
  # join an existing match by id
  python play.py --match-id <id> --name You
  # just watch
  python play.py --match-id <id> --watch
"""

import argparse
import asyncio
import json

import httpx
import websockets


def render(board: list[str]) -> str:
    cells = [mark or str(i) for i, mark in enumerate(board)]
    return "\n".join("  " + " | ".join(cells[r * 3 : r * 3 + 3]) for r in range(3))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server-url", default="http://127.0.0.1:8000")
    ap.add_argument("--match-id", default=None)
    ap.add_argument("--new", action="store_true", help="create a new match first")
    ap.add_argument("--name", default="You")
    ap.add_argument("--watch", action="store_true", help="join as observer (no seat)")
    args = ap.parse_args()
    base = args.server_url.rstrip("/")

    async with httpx.AsyncClient() as http:
        match_id = args.match_id
        if args.new or not match_id:
            match_id = (await http.post(f"{base}/api/v1/lobby/match")).json()["match_id"]
        r = await http.post(
            f"{base}/api/v1/lobby/join",
            json={"match_id": match_id, "player_name": args.name, "spectator": args.watch},
        )
        r.raise_for_status()
        token = r.json()["token"]
    print(f"[match] {match_id}\n[join]  as {args.name}{' (observer)' if args.watch else ''}")

    url = f"{base.replace('http', 'ws', 1)}/ws/match/{match_id}?token={token}"
    my_symbol: str | None = None
    valid: list[int] = []

    async def prompt_and_send(ws: object) -> None:
        while True:
            line = await asyncio.to_thread(
                input, f"[{my_symbol}] your move {valid}  (or 'move | chat text') > "
            )
            move_part, _, chat_part = line.partition("|")
            move_part = move_part.strip()
            try:
                move = int(move_part)
            except ValueError:
                print("  ↳ type a cell number from the legal moves"); continue
            if chat_part.strip():
                await ws.send(json.dumps({"action": "chat", "payload": {"message": chat_part.strip()}}))
            await ws.send(json.dumps({"action": "submit_move", "payload": {"move": move}}))
            return

    try:
        async with websockets.connect(url) as ws:
            async for raw in ws:
                ev = json.loads(raw)
                name, p = ev.get("event"), ev.get("payload") or {}
                my_turn = False
                if name == "joined":
                    my_symbol = p.get("symbol")
                    role = f"you are {my_symbol}" if my_symbol else "observer"
                    print(f"[joined] {role}\n{render(p['board'])}")
                    my_turn = my_symbol is not None and p.get("current_turn") == my_symbol
                    valid = p.get("valid_moves", [])
                elif name == "state_update":
                    lm = p.get("last_move")
                    if lm:
                        print(f"[move]  {lm['player']} → {lm['move']}")
                    print(render(p["board"]))
                    my_turn = my_symbol is not None and p.get("current_turn") == my_symbol
                    valid = p.get("valid_moves", [])
                elif name == "chat_message":
                    print(f"[chat]  {p['sender']}: {p['message']}")
                elif name == "game_over":
                    result = p.get("result")
                    print(f"[over]  result: {result}  ({'draw' if result == 'draw' else result + ' wins'})")
                    break
                elif name == "error":
                    print(f"[error] {p.get('detail')}")
                    my_turn = my_symbol is not None  # let a rejected move be retried
                if my_turn:
                    await prompt_and_send(ws)
    except websockets.ConnectionClosed:
        print("[closed] room closed — bye")


if __name__ == "__main__":
    asyncio.run(main())
