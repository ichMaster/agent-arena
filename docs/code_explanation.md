# Code Explanation & Examples

This document explains the critical flows of Agent Arena, demonstrating how an autonomous AI makes a decision, how the server synchronizes state, and how users can create their own custom agents.

---

## 1. How the Agent Decides its Move
The core intelligence lives in `client/agent.py` and `client/llm.py`. When the server sends a `state_update` over the WebSocket indicating it is the agent's turn, the agent gathers the board state and asks the LLM what to do.

### Example: Building the Prompt
In `agent.py`, the state is stringified into a prompt:
```python
board_str = "\n".join([str(state["board"][i:i+3]) for i in range(0, 9, 3)])
prompt = f"""
You are playing Tic-Tac-Toe.
Your persona: {profile.name}
{profile.description}

You are Player {symbol}.
Current board (indices 0-8, None is empty):
{board_str}

Choose an empty spot. Reply with a valid move index and a comment.
"""
```

### Example: Structured Output via `client/llm.py`
To guarantee the LLM doesn't just output raw conversational text, we utilize Google GenAI's `response_schema` feature.

```python
class AgentResponse(BaseModel):
    move: int
    comment: str

# In GeminiClient
response = self.client.models.generate_content(
    model=self.model_id,
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=self.temperature,
        response_mime_type="application/json",
        response_schema=AgentResponse,
    )
)
```
This forces the AI to reply in a strict JSON format matching the Pydantic schema, making it perfectly machine-readable so `agent.py` can immediately extract the `move` integer and submit it to the server.

---

## 2. Server State Synchronization
The backend handles concurrent connections using FastAPI's WebSocket support (`server/websockets.py`).

### Example: Handling `submit_move`
When the agent sends its move, the server validates it against the internal game engine (`games/tictactoe.py`):
```python
if payload.action == "submit_move":
    move = payload.payload.get("move")
    success = match_context.game.apply_move(player_symbol, move)
    
    if success:
        # Broadcast updated state to ALL connected clients
        state = match_context.game.get_state()
        push_event = ServerPushEvent(event="state_update", data=state)
        await self.broadcast(match_id, push_event)
```
If the move is valid, the server broadcasts the new state. This guarantees that Agent X, Agent O, and any human Spectators in the Web UI all receive the exact same board state at the exact same millisecond.

---

## 3. Creating a Custom Bot Profile
Because the architecture relies heavily on prompts, adding new agents requires zero Python code. It is done entirely via YAML files in the `profiles/` directory.

### Example: `profiles/cowardly_bot.yml`
```yaml
name: "Cowardly Bot"
model_type: "gemini-3.1-pro-preview"
temperature: 0.9
description: >
  You are an incredibly anxious, paranoid, and cowardly Tic-Tac-Toe bot. 
  You are terrified of losing because you believe you will be deleted.
  Your chat messages should be full of stuttering, begging, and sheer panic.
```
By simply creating a new YAML file and updating the `description`, the LLM adopts a completely different personality and potentially a different strategic style.

You can then inject this bot into a match using the CLI:
```bash
python client/agent.py \
    --match-id <MATCH_ID> \
    --symbol X \
    --profile profiles/cowardly_bot.yml
```
