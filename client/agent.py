import asyncio
import argparse
import os
import json
import httpx
import websockets
from dotenv import load_dotenv

# Load environment variables (such as GEMINI_API_KEY)
load_dotenv()

async def get_auth_token(base_url: str, match_id: str, player_name: str) -> str:
    join_url = f"{base_url}/api/v1/lobby/join"
    payload = {
        "match_id": match_id,
        "player_name": player_name
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

async def run_agent(match_id: str, server_url: str, player_name: str) -> None:
    print(f"[*] Starting Agent Client...")
    print(f"[*] Match ID: {match_id}")
    print(f"[*] Server URL: {server_url}")
    print(f"[*] Player Name: {player_name}")
    
    # Check for GEMINI_API_KEY
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        print("[*] GEMINI_API_KEY detected in .env environment")
    else:
        print("[!] Warning: GEMINI_API_KEY not found in environment")
        
    try:
        token = await get_auth_token(server_url, match_id, player_name)
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
                    print(f"[EVENT] state_update: board -> {event_data.get('board')}")
                elif event == "chat_message":
                    sender = event_data.get("sender")
                    msg = event_data.get("message")
                    print(f"[EVENT] chat_message: {sender} -> {msg}")
                elif event == "game_over":
                    winner = event_data.get("winner")
                    print(f"[EVENT] game_over: winner -> {winner}")
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
    parser.add_argument("--player-name", default="Agent", help="The name of the player")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_agent(args.match_id, args.url, args.player_name))
    except KeyboardInterrupt:
        print("\n[*] Shutting down Agent Client...")
