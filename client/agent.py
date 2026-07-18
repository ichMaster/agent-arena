import argparse
import asyncio
import httpx
import websockets
import json
import os
import sys
import random
import os
import sys
from collections import deque
from dotenv import load_dotenv
from client.llm import GeminiClient
from client.profile import load_profile

load_dotenv()

class MemoryWindow:
    def __init__(self, size: int = 10):
        self.buffer = deque(maxlen=size)

    def add_event(self, event_str: str):
        self.buffer.append(event_str)

    def get_context(self) -> str:
        return "\n".join(self.buffer)

async def main():
    parser = argparse.ArgumentParser(description="Agent Arena CLI Client")
    parser.add_argument("--match-id", required=True, help="The UUID of the match to join")
    parser.add_argument("--server", default="http://localhost:8000", help="The HTTP URL of the server")
    parser.add_argument("--profile", required=True, help="Path to the YAML profile configuration")
    
    args = parser.parse_args()
    
    profile = load_profile(args.profile)
    
    match_id = args.match_id
    server_url = args.server.rstrip("/")
    ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://")
    
    print(f"[*] Loaded profile: {profile.name} (Temperature: {profile.temperature}, Memory: {profile.memory_limit})")
    print(f"[*] Joining match {match_id} at {server_url} as {profile.name}...")
    
    # 1. Join Lobby
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{server_url}/api/v1/lobby/join", 
                json={"match_id": match_id, "player_name": profile.name},
                timeout=15.0
            )
            response.raise_for_status()
            token = response.json()["token"]
            print(f"[*] Successfully acquired token: {token}")
    except httpx.RequestError as e:
        print(f"[!] Network error trying to connect to {server_url}: {e}")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"[!] HTTP error: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
        
    # 2. WebSocket Loop
    ws_endpoint = f"{ws_url}/ws/match/{match_id}?token={token}"
    print(f"[*] Connecting to websocket {ws_endpoint}...")
    
    try:
        async with websockets.connect(ws_endpoint) as ws:
            print("[*] WebSocket connected. Listening for events...")
            
            my_symbol = None
            memory = MemoryWindow(size=profile.memory_limit)
            llm_client = GeminiClient(temperature=profile.temperature)
            persona = profile.system_prompt
            
            async for message in ws:
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    print(f"[!] Received invalid JSON: {message}")
                    continue
                    
                event_type = payload.get("event_type")
                data = payload.get("data", {})
                
                if event_type == "connected":
                    my_symbol = data.get("symbol")
                    print(f"[+] Connected to match! Assigned symbol: {my_symbol}")
                    memory.add_event(f"Connected as {my_symbol}")
                    
                elif event_type == "state_update":
                    current_turn = data.get("current_turn")
                    board = data.get("board")
                    print(f"[~] State Update. Board: {board}. Turn: {current_turn}")
                    memory.add_event(f"State Update: Board={board}, Turn={current_turn}")
                    
                    if my_symbol and current_turn == my_symbol:
                        print("[!] It is my turn to move!")
                        valid_moves = [i for i, cell in enumerate(board) if cell is None]
                        prompt = (
                            f"{persona}\n\n"
                            f"Recent History:\n{memory.get_context()}\n\n"
                            f"Current Board: {board}\n"
                            f"Your Symbol: {my_symbol}\n"
                            f"Valid Moves: {valid_moves}\n\n"
                            "Respond with your thoughts and then your move."
                        )
                        print("[*] Hitting Gemini API for next move...")
                        try:
                            for attempt in range(3):
                                response_obj = await llm_client.generate_structured_response(prompt)
                                print(f"[GEMINI RESPONSE]\nMove: {response_obj.move}, Comment: {response_obj.comment}\n[/GEMINI RESPONSE]")
                                
                                if response_obj.move in valid_moves:
                                    await ws.send(json.dumps({"action": "chat", "payload": {"message": response_obj.comment}}))
                                    await ws.send(json.dumps({"action": "submit_move", "payload": {"move": response_obj.move}}))
                                    break
                                else:
                                    print(f"[!] Invalid move {response_obj.move} not in {valid_moves}. Retrying...")
                                    prompt += f"\nError: Move {response_obj.move} is invalid. The valid moves are {valid_moves}. Try again."
                            else:
                                print("[!] Failed 3 times. Falling back to random move.")
                                fallback_move = random.choice(valid_moves)
                                await ws.send(json.dumps({"action": "chat", "payload": {"message": "I'm bored, taking a random spot."}}))
                                await ws.send(json.dumps({"action": "submit_move", "payload": {"move": fallback_move}}))
                                
                        except Exception as e:
                            print(f"[!] Error calling LLM: {e}")
                        
                elif event_type == "chat":
                    msg = data.get("msg", data)
                    print(f"[CHAT] {msg}")
                    memory.add_event(f"Chat: {msg}")
                    
                elif event_type == "error":
                    print(f"[ERROR] {data}")
                    memory.add_event(f"Error: {data}")
                    
                elif event_type == "game_over":
                    print(f"[*] GAME OVER! Winner: {data.get('winner')}")
                    memory.add_event(f"Game Over. Winner: {data.get('winner')}")
                    break
                else:
                    print(f"[?] Unknown event: {event_type} - {data}")
                    
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[*] Connection closed: {e.code} - {e.reason}")
    except Exception as e:
        print(f"[!] WebSocket error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
