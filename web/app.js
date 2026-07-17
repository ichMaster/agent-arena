const API_BASE = "http://127.0.0.1:8000";
const WS_BASE = "ws://127.0.0.1:8000";

let ws = null;
let currentMatchId = null;

// Game State
let currentTurn = null;
let gameActive = false;

// DOM Elements
const hostBtn = document.getElementById('hostBtn');
const joinBtn = document.getElementById('joinBtn');
const matchIdDisplay = document.getElementById('match-id-display');
const connectionDot = document.getElementById('connection-dot');
const statusText = document.getElementById('status-text');

const cardX = document.getElementById('card-x');
const cardO = document.getElementById('card-o');

const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('sendBtn');
const logDiv = document.getElementById('log');

// Bind buttons
hostBtn.addEventListener('click', hostMatch);
joinBtn.addEventListener('click', joinExistingMatch);

// Bind chat
sendBtn.addEventListener('click', sendChatMessage);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendChatMessage();
});

// Bind board cells
const cells = [];
for (let i = 0; i < 9; i++) {
    const cell = document.getElementById(`cell-${i}`);
    cell.addEventListener('click', () => handleCellClick(i));
    cells.push(cell);
}

/**
 * ARENA-028: Lobby HTTP Integration
 */
async function hostMatch() {
    try {
        console.log("Creating new match...");
        const response = await fetch(`${API_BASE}/api/v1/lobby/match`, { method: "POST" });
        if (!response.ok) throw new Error("Failed to create match");
        const data = await response.json();
        
        await connectToMatch(data.match_id);
    } catch (err) {
        console.error(err);
        alert(`Error: ${err.message}`);
    }
}

async function joinExistingMatch() {
    const mid = prompt("Enter Match ID:");
    if (mid && mid.trim() !== "") {
        await connectToMatch(mid.trim());
    }
}

async function connectToMatch(mid) {
    currentMatchId = mid;
    matchIdDisplay.innerText = mid;
    console.log(`Joining match: ${mid}`);
    
    try {
        const joinResp = await fetch(`${API_BASE}/api/v1/lobby/join`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ match_id: mid, player_name: "Human Player" })
        });
        
        if (!joinResp.ok) {
            const errText = await joinResp.text();
            throw new Error(`Join failed: ${errText}`);
        }
        
        const joinData = await joinResp.json();
        const token = joinData.token;
        
        establishWebSocket(mid, token);
    } catch (err) {
        console.error(err);
        alert(`Error connecting to match: ${err.message}`);
        matchIdDisplay.innerText = "None";
    }
}

/**
 * ARENA-029: WebSocket Connection & Event Router
 */
function establishWebSocket(mid, token) {
    if (ws) {
        ws.close();
    }
    
    const wsUrl = `${WS_BASE}/ws/match/${mid}?token=${token}`;
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log("WebSocket Connected!");
        connectionDot.classList.remove('disconnected');
        connectionDot.classList.add('connected');
        statusText.innerText = "Connected";
        
        hostBtn.disabled = true;
        joinBtn.disabled = true;
        
        // Enable Chat (ARENA-031)
        chatInput.disabled = false;
        sendBtn.disabled = false;
        
        renderSystemMessage("Connected to match server.");
    };
    
    ws.onclose = (event) => {
        console.log("WebSocket Disconnected", event);
        connectionDot.classList.remove('connected');
        connectionDot.classList.add('disconnected');
        statusText.innerText = "Disconnected";
        
        hostBtn.disabled = false;
        joinBtn.disabled = false;
        chatInput.disabled = true;
        sendBtn.disabled = true;
        gameActive = false;
        
        renderSystemMessage("Disconnected from server.");
    };
    
    ws.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            if (payload.error) {
                console.error("Server Error:", payload.error);
                return;
            }
            
            switch(payload.event) {
                case "state_update":
                    renderBoard(payload.data);
                    break;
                case "game_over":
                    handleGameOver(payload.data);
                    break;
                case "chat_message":
                    renderChat(payload.data);
                    break;
            }
        } catch (e) {
            console.error("Error parsing message:", e);
        }
    };
}

/**
 * ARENA-030: Board Reactivity & Gameplay Controls
 */
function renderBoard(data) {
    gameActive = data.status === "ACTIVE" || data.status === "PENDING" || data.status === null;
    currentTurn = data.current_turn;
    
    // Update player cards
    if (currentTurn === 'X') {
        cardX.classList.add('active');
        cardO.classList.remove('active');
    } else if (currentTurn === 'O') {
        cardO.classList.add('active');
        cardX.classList.remove('active');
    } else {
        cardX.classList.remove('active');
        cardO.classList.remove('active');
    }
    
    // Update grid cells
    if (data.board) {
        for (let i = 0; i < 9; i++) {
            const val = data.board[i];
            const cell = cells[i];
            
            // Clear previous state
            cell.innerText = "";
            cell.classList.remove('x', 'o', 'disabled');
            
            if (val === 'X') {
                cell.innerText = "X";
                cell.classList.add('x', 'disabled');
            } else if (val === 'O') {
                cell.innerText = "O";
                cell.classList.add('o', 'disabled');
            } else {
                // Empty cell
                if (gameActive && currentTurn === 'X') {
                    // Clickable for Human
                    cell.classList.remove('disabled');
                } else {
                    cell.classList.add('disabled');
                }
            }
        }
    }
}

function handleCellClick(index) {
    if (!gameActive) return;
    if (currentTurn !== 'X') return; // Human is X
    
    const cell = cells[index];
    if (cell.classList.contains('disabled')) return;
    
    // Send move to server
    if (ws && ws.readyState === WebSocket.OPEN) {
        const payload = {
            action: "submit_move",
            payload: { move: index }
        };
        ws.send(JSON.stringify(payload));
    }
}

/**
 * ARENA-031: Chat Interface & Game Over
 */
function sendChatMessage() {
    const text = chatInput.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
    
    const payload = {
        action: "chat_message",
        payload: { sender: "Human Player", message: text }
    };
    ws.send(JSON.stringify(payload));
    chatInput.value = "";
}

function renderChat(data) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('msg');
    
    if (data.sender === "Human Player") {
        msgDiv.classList.add('user');
        msgDiv.innerHTML = `<span class="sender">You:</span> ${data.message}`;
    } else {
        msgDiv.classList.add('agent');
        msgDiv.innerHTML = `<span class="sender">${data.sender}:</span> ${data.message}`;
    }
    
    logDiv.appendChild(msgDiv);
    logDiv.scrollTop = logDiv.scrollHeight;
}

function renderSystemMessage(text) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('msg', 'system');
    msgDiv.innerText = text;
    logDiv.appendChild(msgDiv);
    logDiv.scrollTop = logDiv.scrollHeight;
}

function handleGameOver(data) {
    gameActive = false;
    currentTurn = null;
    
    cardX.classList.remove('active');
    cardO.classList.remove('active');
    
    // Disable all cells
    cells.forEach(cell => cell.classList.add('disabled'));
    
    let endMessage = "";
    if (data.winner === "X") {
        endMessage = "Game Over! You won! 🎉";
        statusText.innerText = "Winner: You";
    } else if (data.winner === "O") {
        endMessage = "Game Over! Agent won. 🤖";
        statusText.innerText = "Winner: Agent";
    } else {
        endMessage = "Game Over! It's a draw. 🤝";
        statusText.innerText = "Draw";
    }
    
    renderSystemMessage(endMessage);
}
