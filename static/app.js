let ws = null;
let currentMatchId = null;
let currentToken = null;

// DOM Elements
const hostBtn = document.getElementById("hostBtn");
const joinBtn = document.getElementById("joinBtn");
const connectionDot = document.getElementById("connection-dot");
const statusText = document.getElementById("status-text");
const matchIdDisplay = document.getElementById("match-id-display");
const chatMessages = document.getElementById("chat-messages");

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
        await joinMatch(matchId, "Player 1");
    } catch (err) {
        addSystemMessage(`Host Error: ${err.message}`);
    }
}

async function joinMatchPrompt() {
    const matchId = prompt("Enter Match UUID to Join:");
    if (matchId) {
        const cleanMatchId = matchId.trim();
        if (cleanMatchId) {
            await joinMatch(cleanMatchId, "Player 2");
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
    };
    
    ws.onclose = (event) => {
        connectionDot.className = "status-dot disconnected";
        statusText.textContent = "Disconnected";
        addSystemMessage(`Connection closed (code: ${event.code})`);
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
            addSystemMessage(`State Update received: board -> [${eventData.board.map(v => v || '-').join(', ')}]`);
            break;
        case "chat_message":
            addChatMessage(eventData.sender, eventData.message);
            break;
        case "game_over":
            addSystemMessage(`Game Over! Winner: ${eventData.winner}`);
            break;
        default:
            console.warn("Unhandled server event:", event);
    }
}

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

// Event listeners
hostBtn.addEventListener("click", hostMatch);
joinBtn.addEventListener("click", joinMatchPrompt);
