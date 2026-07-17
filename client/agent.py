import asyncio
import aiohttp
import argparse
import os
import json
import websockets
from dotenv import load_dotenv
from client.llm import GeminiClient

# Load environment variables
load_dotenv()

class MemoryWindow:
    def __init__(self, limit=10):
        self.limit = limit
        self.history = []
        
    def add(self, event_str: str):
        self.history.append(event_str)
        if len(self.history) > self.limit:
            self.history.pop(0)
            
    def get_context(self) -> str:
        return "\n".join(self.history)


async def get_auth_token(base_url: str, match_id: str) -> str:
    join_url = f"{base_url}/api/v1/lobby/join"
    payload = {
        "match_id": match_id,
        "player_name": "AI Agent"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(join_url, json=payload) as response:
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(f"Failed to join match {match_id}: {text}")
            
            data = await response.json()
            return data["token"]

async def run_agent(match_id: str, server_url: str, symbol: str):
    print(f"[*] Booting Agent CLI (Symbol: {symbol})")
    print(f"[*] Target Match ID: {match_id}")
    print(f"[*] Server URL: {server_url}")
    
    memory = MemoryWindow()
    llm_client = GeminiClient()

    # Check for GEMINI_API_KEY as requested
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        print("[*] Gemini API Key loaded successfully.")
    else:
        print("[!] Warning: GEMINI_API_KEY not found in .env.")

    # 1. Fetch token
    try:
        token = await get_auth_token(server_url, match_id)
        print(f"[+] Successfully fetched Auth Token: {token}")
    except Exception as e:
        print(f"[-] Error joining lobby: {e}")
        return

    # 2. Connect to WebSocket
    ws_base = server_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base}/ws/match/{match_id}?token={token}"
    
    print(f"[*] Connecting to WebSocket: {ws_url}")
    try:
        async with websockets.connect(ws_url) as websocket:
            print("[+] WebSocket connected successfully. Listening for events...")
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    print(f"[-] Received invalid JSON payload: {message}")
                    continue
                
                # Check for error payload (not standard event struct)
                if "error" in data:
                    print(f"[!] ERROR Payload: {data['error']}")
                    continue
                
                event_type = data.get("event")
                payload = data.get("data", {})
                
                if event_type == "state_update":
                    turn = payload.get('current_turn')
                    status = payload.get('status')
                    board = payload.get('board')
                    print(f"[EVENT] State Update: Turn -> {turn} | Status -> {status}")
                    
                    # Log state to memory
                    memory.add(f"Board State: {board} | Current Turn: {turn}")
                    
                    # Evaluate if it's our turn
                    if turn == symbol and status == "ACTIVE":
                        print(f"[*] It is my turn ({symbol})! Generating prompt...")
                        valid_moves = [i for i, cell in enumerate(board) if cell is None]
                        
                        prompt = f"""
You are an arrogant Tic-Tac-Toe master. Never lose.
You are playing as '{symbol}'.

Recent History:
{memory.get_context()}

Current Board: {board}
Valid Moves (Indices): {valid_moves}

It is your turn. Please state your move (0-8) and provide a short, arrogant comment.
"""
                        print("[*] Prompt constructed. Hitting Gemini API...")
                        max_attempts = 3
                        attempt = 0
                        llm_move = None
                        llm_comment = None
                        
                        while attempt < max_attempts:
                            try:
                                response = await llm_client.generate_response(prompt)
                                move = response.move
                                comment = response.comment
                                print(f"\n[GEMINI RESPONSE]\nMove: {move}\nComment: {comment}\n-----------------")
                                
                                if move in valid_moves:
                                    print(f"[+] Valid move chosen: {move}")
                                    llm_move = move
                                    llm_comment = comment
                                    break
                                else:
                                    print(f"[-] Invalid move generated: {move}. Retrying...")
                                    prompt += f"\nError: Move {move} is invalid. The valid moves are {valid_moves}. Try again."
                            except Exception as e:
                                print(f"[-] LLM Generation failed on attempt {attempt+1}: {e}")
                            
                            attempt += 1
                            
                        # If loop exhausted without valid move, pick random
                        if llm_move is None:
                            import random
                            llm_move = random.choice(valid_moves)
                            llm_comment = "I'm experiencing an anomaly, but this move will suffice."
                            print(f"[!] Fallback to random move: {llm_move}")
                            
                        # Send Chat Comment
                        print("[*] Submitting payloads to server...")
                        if llm_comment:
                            chat_payload = {
                                "action": "chat",
                                "payload": {"message": llm_comment}
                            }
                            await websocket.send(json.dumps(chat_payload))
                            
                        # Send Move
                        move_payload = {
                            "action": "submit_move",
                            "payload": {"move": llm_move}
                        }
                        await websocket.send(json.dumps(move_payload))
                        
                elif event_type == "chat_message":
                    sender = payload.get('sender')
                    msg = payload.get('message')
                    print(f"[CHAT] {sender}: {msg}")
                    memory.add(f"Chat from {sender}: {msg}")
                elif event_type == "game_over":
                    winner = payload.get('winner')
                    print(f"[EVENT] GAME OVER! Winner: {winner}")
                    memory.add(f"Game Over. Winner: {winner}")
                else:
                    print(f"[*] Unknown event type '{event_type}': {payload}")

    except websockets.exceptions.ConnectionClosed as e:
        print(f"[*] Connection closed gracefully (code: {e.code}, reason: {e.reason})")
    except Exception as e:
        print(f"[-] WebSocket connection error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Arena CLI Client")
    parser.add_argument("--match-id", required=True, help="The UUID of the match to join")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the Game Server")
    parser.add_argument("--symbol", default="O", help="Symbol the agent is playing as (X or O)")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_agent(args.match_id, args.url, args.symbol))
    except KeyboardInterrupt:
        print("\n[*] Shutting down Agent CLI...")
