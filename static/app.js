let ws = null;
let currentMatchId = null;
let currentToken = null;
let assignedSymbol = null; // 'X' or 'O' or 'Spectator'
let currentTurn = null; // 'X' or 'O'
let isGameActive = false;
let currentPlayerName = "Player";

// DOM Elements
const hostBtn = document.getElementById("hostBtn");
const joinBtn = document.getElementById("joinBtn");
const connectionDot = document.getElementById("connection-dot");
const statusText = document.getElementById("status-text");
const matchIdDisplay = document.getElementById("match-id-display");
const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("sendBtn");
const cardX = document.getElementById("card-x");
const cardO = document.getElementById("card-o");

// Setup Cell click listeners
const cells = [];
for (let i = 0; i < 9; i++) {
    const cell = document.getElementById(`cell-${i}`);
    cells.push(cell);
    cell.addEventListener("click", () => handleCellClick(i));
}

// Lobby Functions
async function hostMatch() {
    addSystemMessage("Creating new match...");
    try {
        const response = await fetch("/api/v1/lobby/match", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            }
        });
        if (!response.ok) {
            throw new Error(`Server returned status ${response.status}`);
        }
        const data = await response.json();
        const matchId = data.match_id;
        addSystemMessage(`Hosted match: ${matchId}`);
        currentPlayerName = "Host_Human";
        await joinMatch(matchId, currentPlayerName);
    } catch (err) {
        addSystemMessage(`Host Error: ${err.message}`);
    }
}

async function joinMatchPrompt() {
    const matchId = prompt("Enter Match UUID to Join:");
    if (matchId) {
        const cleanMatchId = matchId.trim();
        if (cleanMatchId) {
            currentPlayerName = "Joiner_Human";
            await joinMatch(cleanMatchId, currentPlayerName);
        }
    }
}

async function joinMatch(matchId, playerName) {
    addSystemMessage(`Joining match ${matchId} as ${playerName}...`);
    try {
        const response = await fetch("/api/v1/lobby/join", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                match_id: matchId,
                player_name: playerName
            })
        });
        if (!response.ok) {
            throw new Error(`Server returned status ${response.status}`);
        }
        const data = await response.json();
        const token = data.token;
        
        currentMatchId = matchId;
        currentToken = token;
        
        // Update DOM displays
        matchIdDisplay.textContent = matchId;
        
        // Connect WebSocket
        connectWebSocket(matchId, token);
    } catch (err) {
        addSystemMessage(`Join Error: ${err.message}`);
    }
}

// WebSocket Connection
function connectWebSocket(matchId, token) {
    if (ws) {
        ws.close();
    }
    
    const loc = window.location;
    const wsProto = loc.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProto}//${loc.host}/ws/match/${matchId}?token=${token}`;
    
    addSystemMessage(`Connecting to WebSocket: ${wsUrl}`);
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        connectionDot.className = "status-dot connected";
        statusText.textContent = "Server Connected";
        addSystemMessage("Server connection active!");
        
        // Enable chat input
        chatInput.removeAttribute("disabled");
        sendBtn.removeAttribute("disabled");
    };
    
    ws.onclose = (event) => {
        connectionDot.className = "status-dot disconnected";
        statusText.textContent = "Disconnected";
        addSystemMessage(`Connection closed (code: ${event.code})`);
        
        // Disable chat input
        chatInput.setAttribute("disabled", "true");
        sendBtn.setAttribute("disabled", "true");
        
        isGameActive = false;
        updateControlsState();
    };
    
    ws.onerror = (err) => {
        addSystemMessage(`WebSocket error occurred`);
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleServerEvent(data);
        } catch (e) {
            console.error("Failed to parse message JSON:", event.data, e);
        }
    };
}

// Event Router
function handleServerEvent(data) {
    if (data.error) {
        addSystemMessage(`[ERROR] ${data.error}`);
        return;
    }
    
    const event = data.event;
    const eventData = data.data;
    
    console.log(`[WS EVENT] ${event}:`, eventData);
    
    switch (event) {
        case "state_update":
            if (eventData.assigned_symbol) {
                assignedSymbol = eventData.assigned_symbol;
                addSystemMessage(`You are registered as player: ${assignedSymbol}`);
            }
            currentTurn = eventData.current_turn;
            isGameActive = eventData.status === "ACTIVE";
            
            renderBoard(eventData.board);
            renderTurnIndicators();
            updateControlsState();
            break;
            
        case "chat_message":
            addChatMessage(eventData.sender, eventData.message);
            break;
            
        case "game_over":
            isGameActive = false;
            addSystemMessage(`Game Over! Winner: ${eventData.winner}`);
            statusText.textContent = `Game Over: Winner ${eventData.winner}`;
            updateControlsState();
            break;
            
        default:
            console.warn("Unhandled server event:", event);
    }
}

// Render game state
function renderBoard(board) {
    for (let i = 0; i < 9; i++) {
        const cellVal = board[i]; // 'X', 'O', or null
        const cellEl = cells[i];
        
        // Reset classes
        cellEl.className = "cell";
        
        if (cellVal === "X") {
            cellEl.textContent = "X";
            cellEl.classList.add("x");
        } else if (cellVal === "O") {
            cellEl.textContent = "O";
            cellEl.classList.add("o");
        } else {
            cellEl.textContent = "";
        }
    }
}

function renderTurnIndicators() {
    cardX.classList.remove("active");
    cardO.classList.remove("active");
    
    if (currentTurn === "X") {
        cardX.classList.add("active");
    } else if (currentTurn === "O") {
        cardO.classList.add("active");
    }
}

function updateControlsState() {
    // A cell is playable if the game is active, it's our turn, and cell is empty
    const ourTurn = (assignedSymbol === currentTurn);
    
    for (let i = 0; i < 9; i++) {
        const cellEl = cells[i];
        const isEmpty = (cellEl.textContent === "");
        
        if (isGameActive && ourTurn && isEmpty) {
            cellEl.classList.remove("disabled");
        } else {
            cellEl.classList.add("disabled");
        }
    }
}

// Handle client inputs
function handleCellClick(index) {
    if (!isGameActive) return;
    if (assignedSymbol !== currentTurn) {
        addSystemMessage("It is not your turn!");
        return;
    }
    if (cells[index].textContent !== "") {
        addSystemMessage("Cell is already occupied!");
        return;
    }
    
    // Send move
    const movePayload = {
        action: "submit_move",
        payload: {
            move: index
        }
    };
    ws.send(JSON.stringify(movePayload));
}

function sendChatMessage() {
    const text = chatInput.value.trim();
    if (!text) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    
    const chatPayload = {
        action: "chat_message",
        payload: {
            sender: currentPlayerName,
            message: text
        }
    };
    ws.send(JSON.stringify(chatPayload));
    chatInput.value = "";
}

// Chat input listeners
sendBtn.addEventListener("click", sendChatMessage);
chatInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
        sendChatMessage();
    }
});

// Helpers to append elements to messaging panel
function addSystemMessage(text) {
    const div = document.createElement("div");
    div.className = "message system";
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addChatMessage(sender, text) {
    const div = document.createElement("div");
    // Classify as agent or user depending on sender
    if (sender.toLowerCase().includes("agent") || sender.toLowerCase().includes("bot")) {
        div.className = "message agent";
        div.innerHTML = `<span class="name">${sender}</span>${text}`;
    } else {
        div.className = "message user";
        div.textContent = `${sender}: ${text}`;
    }
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Event listeners for Lobby controls
hostBtn.addEventListener("click", hostMatch);
joinBtn.addEventListener("click", joinMatchPrompt);
