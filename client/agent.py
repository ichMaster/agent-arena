import asyncio
import aiohttp
import argparse
import os
import json
import websockets
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

async def run_agent(match_id: str, server_url: str):
    print(f"[*] Booting Agent CLI")
    print(f"[*] Target Match ID: {match_id}")
    print(f"[*] Server URL: {server_url}")

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
                    print(f"[EVENT] State Update: Turn -> {payload.get('current_turn')} | Status -> {payload.get('status')}")
                    # Placeholder: Evaluate if it's our turn
                elif event_type == "chat_message":
                    print(f"[CHAT] {payload.get('sender')}: {payload.get('message')}")
                elif event_type == "game_over":
                    print(f"[EVENT] GAME OVER! Winner: {payload.get('winner')}")
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
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_agent(args.match_id, args.url))
    except KeyboardInterrupt:
        print("\n[*] Shutting down Agent CLI...")
