"""The WebSocket protocol layer — ConnectionManager, envelopes, and event builders (§5.3, §6.2).

Pure and DB-free: the ``ConnectionManager`` is the in-memory socket registry (the only in-memory
server state, §10), and the event builders are pure functions producing the §6.2 wire shapes. The
endpoint/handlers gather the data (reconstructing state from the Repository) and call these builders.

This module pins the §6.2 wire seam — a change to an event/action shape updates architecture.md §6.2
and the contract test (tests/test_ws_protocol.py) in the same commit.
"""

import json
from typing import Any

from fastapi import WebSocket

# --- Envelopes & event builders (§6.2) --------------------------------------


def event(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap a server->client event: ``{"event": name, "payload": {...}}``."""
    return {"event": name, "payload": payload}


def joined_event(
    symbol: str | None, board: list[Any], current_turn: str | None, valid_moves: list[Any]
) -> dict[str, Any]:
    return event(
        "joined",
        {"symbol": symbol, "board": board, "current_turn": current_turn, "valid_moves": valid_moves},
    )


def state_update_event(
    board: list[Any],
    current_turn: str | None,
    valid_moves: list[Any],
    last_move: dict[str, Any] | None,
) -> dict[str, Any]:
    return event(
        "state_update",
        {
            "board": board,
            "current_turn": current_turn,
            "valid_moves": valid_moves,
            "last_move": last_move,
        },
    )


def chat_message_event(sender: str, message: str) -> dict[str, Any]:
    return event("chat_message", {"sender": sender, "message": message})


def game_over_event(result: str) -> dict[str, Any]:
    return event("game_over", {"result": result})


def error_event(detail: str) -> dict[str, Any]:
    return event("error", {"detail": detail})


def parse_action(message: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """Parse an inbound client->server ``{action, payload}``; returns ``(action, payload)``."""
    raw_action = message.get("action")
    action = raw_action if isinstance(raw_action, str) else None
    raw_payload = message.get("payload")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    return action, payload


# --- ConnectionManager (§5.3) -----------------------------------------------


class ConnectionManager:
    """Per-match live sockets + owner map. Touched only from the single event loop (§10)."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}
        self._owners: dict[WebSocket, str] = {}

    async def connect(self, match_id: str, websocket: WebSocket, participant_id: str) -> None:
        await websocket.accept()
        self._connections.setdefault(match_id, []).append(websocket)
        self._owners[websocket] = participant_id

    def disconnect(self, match_id: str, websocket: WebSocket) -> str | None:
        """Remove the socket and return its owner's participant_id (or ``None`` if unknown)."""
        sockets = self._connections.get(match_id)
        if sockets is not None and websocket in sockets:
            sockets.remove(websocket)
            if not sockets:
                del self._connections[match_id]
        return self._owners.pop(websocket, None)

    async def broadcast(self, match_id: str, event_message: dict[str, Any]) -> None:
        """Serialize once, then send to each socket — pruning one that fails so the rest deliver."""
        data = json.dumps(event_message)
        for websocket in list(self._connections.get(match_id, [])):
            try:
                await websocket.send_text(data)
            except Exception:
                self.disconnect(match_id, websocket)

    async def send_to(self, websocket: WebSocket, event_message: dict[str, Any]) -> None:
        await websocket.send_text(json.dumps(event_message))

    async def close_room(self, match_id: str) -> None:
        """Close every socket in a finished match, then clear the room."""
        for websocket in list(self._connections.get(match_id, [])):
            try:
                await websocket.close()
            except Exception:
                pass
            self.disconnect(match_id, websocket)

    def connection_count(self, match_id: str) -> int:
        return len(self._connections.get(match_id, []))
