# Agent Arena - Web UI Specification

## 1. Overview
The Web UI is the primary interface for human players to participate in matches and observe agent behavior. It is designed as a lightweight, single-page application (SPA) built using Vanilla HTML, CSS, and Javascript to avoid heavy framework overhead. It maintains a persistent native WebSocket connection to the Game Server. The visual implementation must strictly adhere to the high-fidelity aesthetic established in `ui_prototype.html`.

## 2. Design System & Aesthetics
The application utilizes a premium, dark-mode "Glassmorphism" design system to create a dynamic, modern feel.
- **Color Palette & Theme:**
  - **Background:** Deep slate radial gradient (`#1e293b` expanding to `#0f172a`).
  - **Panels:** Translucent slate (`rgba(30, 41, 59, 0.7)`) with a strong CSS `backdrop-filter: blur(16px)`.
  - **Primary Accent (Human/X):** Glowing Blue (`#3b82f6`) with a drop-shadow glow.
  - **Agent Accent (Agent/O):** Glowing Pink (`#ec4899`) with a drop-shadow glow.
- **Typography:** Google Fonts 'Inter' for clean, readable sans-serif text.
- **Micro-Animations:** Interactive elements (like grid cells and buttons) feature `translateY` hover lifts, and incoming chat messages utilize keyframe fade-in animations to feel responsive and alive.

## 3. Structural Components
The UI is divided into two primary responsive panels inside a central flex container.

### 3.1 The Game Area (Main Panel)
This panel renders the active game module and match metadata.
- **Header Status:** Displays the game title alongside a glowing Server Status dot (green when the WebSocket is connected, red when disconnected) and the active `match_id`.
- **The Board Grid:** A CSS Grid layout (initially 3x3 for Tic-Tac-Toe). Each empty cell listens for human `click` events to fire moves. When the server confirms a move, the cell updates with an `.x` or `.o` class, triggering the neon glow effect.
- **Player Status Cards:** Located at the bottom, these cards display the Human Player and the Agent. An `.active` CSS class shifts between the cards to visually indicate whose turn it is, driven entirely by the server's `your_turn` events.

### 3.2 The Chat Area (Sidebar Panel)
This panel handles real-time communication between all entities in the match.
- **Message Ledger:** A scrollable container holding the chat history. Messages are styled distinctly based on the sender:
  - *System Messages:* Muted text, centered, translucent background (e.g., "Agent placed O at Center").
  - *User Messages:* Right-aligned, blue accent bubble.
  - *Agent Messages:* Left-aligned, pink accent bubble featuring a bold `name` badge to identify which specific agent is speaking.
- **Input Mechanism:** A text input field and 'Send' button that intercepts `Enter` key presses or clicks to emit chat payloads to the server.

## 4. WebSocket Integration & State Management
The final implementation (`web/app.js`) will strip out the hardcoded `setTimeout` fake-logic from the prototype and replace it with a purely event-driven WebSocket controller.

- **Initialization:** On page load, the client opens a WebSocket connection to `wss://server_url/ws/match/{match_id}`.
- **Handling Inbound Events (Push from Server):**
  - `onmessage` routes incoming JSON payloads based on the `event` type.
  - `chat_message`: Appends a new message DOM element to the Chat Area.
  - `move_made`: Updates the specific cell on the Board Grid, logs a system message, and shifts the `.active` player card.
  - `your_turn`: Unlocks the board grid for clicking, signaling the human can act.
- **Handling Outbound Actions (Payloads to Server):**
  - When a human clicks an unlocked grid cell, the client sends: `{"action": "submit_move", "move": index}`.
  - When a human submits the chat form, the client sends: `{"action": "send_chat_message", "content": text}`.
  
The Web UI stores **no authoritative game state**. It functions entirely as a "dumb terminal" that blindly renders whatever state the Game Server pushes to it.
