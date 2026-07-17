const API_BASE = "http://127.0.0.1:8000";
const WS_BASE = "ws://127.0.0.1:8000";

let ws = null;
let currentMatchId = null;

// DOM Elements
const hostBtn = document.getElementById('hostBtn');
const joinBtn = document.getElementById('joinBtn');
const matchIdDisplay = document.getElementById('match-id-display');
const connectionDot = document.getElementById('connection-dot');
const statusText = document.getElementById('status-text');

// Bind buttons
hostBtn.addEventListener('click', hostMatch);
joinBtn.addEventListener('click', joinExistingMatch);

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
        // 1. Fetch Auth Token
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
        
        // 2. Establish WebSocket (ARENA-029)
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
        
        // Disable lobby buttons to prevent re-entry logic bugs for now
        hostBtn.disabled = true;
        joinBtn.disabled = true;
    };
    
    ws.onclose = (event) => {
        console.log("WebSocket Disconnected", event);
        connectionDot.classList.remove('connected');
        connectionDot.classList.add('disconnected');
        statusText.innerText = "Disconnected";
        
        hostBtn.disabled = false;
        joinBtn.disabled = false;
    };
    
    ws.onerror = (error) => {
        console.error("WebSocket Error:", error);
    };
    
    ws.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            
            // Handle raw error messages from server
            if (payload.error) {
                console.error("Server Error:", payload.error);
                return;
            }
            
            // Route events
            switch(payload.event) {
                case "state_update":
                    console.log("[Event: state_update]", payload.data);
                    // TODO: Reactively update board cells (v04.03)
                    break;
                case "game_over":
                    console.log("[Event: game_over]", payload.data);
                    // TODO: Show game over state (v04.03)
                    break;
                case "chat_message":
                    console.log("[Event: chat_message]", payload.data);
                    // TODO: Render message in chat ledger (v04.03)
                    break;
                default:
                    console.log("Unknown event received:", payload);
            }
        } catch (e) {
            console.error("Error parsing WebSocket message:", e, event.data);
        }
    };
}
