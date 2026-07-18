import asyncio
import argparse
import os
import json
import random
import httpx
import websockets
from dotenv import load_dotenv
from pydantic import BaseModel
from client.llm import GeminiClient
from client.memory import MemoryWindow
from client.profile import AgentProfile

# Load environment variables (such as GEMINI_API_KEY)
load_dotenv()

class AgentResponse(BaseModel):
    move: int
    comment: str

async def get_auth_token(base_url: str, match_id: str, player_name: str, symbol: str) -> str:
    join_url = f"{base_url}/api/v1/lobby/join"
    payload = {
        "match_id": match_id,
        "player_name": player_name,
        "symbol": symbol
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(join_url, json=payload)
        except Exception as e:
            raise RuntimeError(f"Server is offline or unreachable: {e}")
            
        if response.status_code != 200:
            raise RuntimeError(f"Failed to join lobby: status code {response.status_code}, response: {response.text}")
            
        token = response.json()["token"]
        return str(token)

async def run_agent(match_id: str, server_url: str, symbol: str, profile_path: str) -> None:
    print(f"[*] Loading profile config: {profile_path}...")
    profile = AgentProfile.load_from_yaml(profile_path)
    
    print(f"[*] Starting Agent Client: '{profile.name}'...")
    print(f"[*] Model ID: {profile.model_type}")
    print(f"[*] Temperature: {profile.temperature}")
    print(f"[*] Memory Limit: {profile.memory_limit}")
    print(f"[*] Match ID: {match_id}")
    print(f"[*] Server URL: {server_url}")
    print(f"[*] Symbol: {symbol}")
    
    memory = MemoryWindow(limit=profile.memory_limit)
    llm_client = GeminiClient(model_id=profile.model_type, temperature=profile.temperature)
    
    # Check for GEMINI_API_KEY
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        print("[*] GEMINI_API_KEY detected in .env environment")
    else:
        print("[!] Warning: GEMINI_API_KEY not found in environment")
        
    try:
        token = await get_auth_token(server_url, match_id, profile.name, symbol)
        print(f"[+] Acquired Auth Token: {token}")
    except Exception as e:
        print(f"[-] HTTP Error: {e}")
        return
        
    # Translate HTTP URL to WebSocket URL
    ws_base = server_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base}/ws/match/{match_id}?token={token}"
    
    print(f"[*] Connecting to WebSocket: {ws_url}")
    try:
        async with websockets.connect(ws_url) as ws:
            print("[+] WebSocket connection established. Listening for events...")
            async for message in ws:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    msg_str = message.decode("utf-8") if isinstance(message, bytes) else str(message)
                    print(f"[-] Received invalid JSON payload: {msg_str}")
                    continue
                    
                if "error" in data:
                    print(f"[!] Server Error: {data['error']}")
                    continue
                    
                event = data.get("event")
                event_data = data.get("data", {})
                
                if event == "state_update":
                    board = event_data.get('board')
                    current_turn = event_data.get('current_turn')
                    status = event_data.get('status')
                    print(f"[EVENT] state_update: board -> {board} | current_turn -> {current_turn} | status -> {status}")
                    
                    # Log state to memory
                    memory.add(f"Board State: {board} | Current Turn: {current_turn}")
                    
                    # Check if it is the agent's turn
                    if current_turn == symbol and status == "ACTIVE":
                        print(f"[*] It is my turn ({symbol})! Formulating structured prompt...")
                        valid_moves = [i for i, cell in enumerate(board) if cell is None]
                        
                        prompt_error_ctx = ""
                        chosen_move = None
                        chosen_comment = ""
                        max_attempts = 3
                        
                        for attempt in range(max_attempts):
                            prompt = f"""
System Persona: {profile.system_prompt}

Recent History:
{memory.get_context()}

Current Board: {board}
Valid Moves (Indices): {valid_moves}
{prompt_error_ctx}
It is your turn. Please state your move (0-8) and provide a short comment that fits your persona.
"""
                            print(f"[*] Hitting LLM API (Attempt {attempt+1}/{max_attempts})...")
                            try:
                                response_obj = await asyncio.wait_for(
                                    llm_client.generate_structured_response(prompt, AgentResponse),
                                    timeout=15.0
                                )
                                move = response_obj.move
                                comment = response_obj.comment
                                print(f"[+] LLM output: chosen move -> {move} | comment -> '{comment}'")
                                
                                if move in valid_moves:
                                    chosen_move = move
                                    chosen_comment = comment
                                    break
                                else:
                                    print(f"[!] Hallucinated invalid move: {move}")
                                    prompt_error_ctx = f"\nError: Move {move} is invalid. The valid moves are {valid_moves}. Try again.\n"
                            except Exception as e:
                                print(f"[-] LLM generation error: {e}")
                                prompt_error_ctx = f"\nError during LLM API call: {e}. Try again.\n"
                                
                        # Fallback if no valid move was selected after retries
                        if chosen_move is None:
                            chosen_move = random.choice(valid_moves)
                            chosen_comment = "Bah, my algorithms are temporarily computing universe structures, this move will suffice."
                            print(f"[!] Fallback to random move: {chosen_move}")
                            
                        # Send chat message comment
                        chat_payload = {
                            "action": "chat_message",
                            "payload": {
                                "sender": profile.name,
                                "message": chosen_comment
                            }
                        }
                        await ws.send(json.dumps(chat_payload))
                        
                        # Send move payload
                        move_payload = {
                            "action": "submit_move",
                            "payload": {
                                "move": chosen_move
                            }
                        }
                        await ws.send(json.dumps(move_payload))
                        print(f"[+] Sent move {chosen_move} and chat comment to server")
                            
                elif event == "chat_message":
                    sender = event_data.get("sender")
                    msg = event_data.get("message")
                    print(f"[EVENT] chat_message: {sender} -> {msg}")
                    memory.add(f"Chat from {sender}: {msg}")
                    
                elif event == "game_over":
                    winner = event_data.get("winner")
                    print(f"[EVENT] game_over: winner -> {winner}")
                    memory.add(f"Game Over. Winner: {winner}")
                    
                else:
                    print(f"[EVENT] Unknown event '{event}': {event_data}")
                    
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[*] Connection closed gracefully (code: {e.code}, reason: {e.reason})")
    except Exception as e:
        print(f"[-] WebSocket Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Arena CLI Client")
    parser.add_argument("--match-id", required=True, help="The UUID of the match to join")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the Game Server")
    parser.add_argument("--symbol", default="X", help="Symbol the agent plays as (X or O)")
    parser.add_argument("--profile", required=True, help="Path to the YAML agent profile definition")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_agent(args.match_id, args.url, args.symbol, args.profile))
    except KeyboardInterrupt:
        print("\n[*] Shutting down Agent Client...")
