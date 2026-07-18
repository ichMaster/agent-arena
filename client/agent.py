import argparse
import asyncio
import httpx
import websockets
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()

async def main():
    parser = argparse.ArgumentParser(description="Agent Arena CLI Client")
    parser.add_argument("--match-id", required=True, help="The UUID of the match to join")
    parser.add_argument("--server", default="http://localhost:8000", help="The HTTP URL of the server")
    parser.add_argument("--name", default="AgentBot", help="The player name to register as")
    
    args = parser.parse_args()
    
    match_id = args.match_id
    server_url = args.server.rstrip("/")
    ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://")
    
    print(f"[*] Joining match {match_id} at {server_url} as {args.name}...")
    
    # 1. Join Lobby
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{server_url}/api/v1/lobby/join", 
                json={"match_id": match_id, "player_name": args.name},
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
                    
                elif event_type == "state_update":
                    current_turn = data.get("current_turn")
                    print(f"[~] State Update. Board: {data.get('board')}. Turn: {current_turn}")
                    if my_symbol and current_turn == my_symbol:
                        print("[!] It is my turn to move!")
                        
                elif event_type == "chat":
                    print(f"[CHAT] {data}")
                    
                elif event_type == "error":
                    print(f"[ERROR] {data}")
                    
                elif event_type == "game_over":
                    print(f"[*] GAME OVER! Winner: {data.get('winner')}")
                    break
                else:
                    print(f"[?] Unknown event: {event_type} - {data}")
                    
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[*] Connection closed: {e.code} - {e.reason}")
    except Exception as e:
        print(f"[!] WebSocket error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
