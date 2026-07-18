let ws = null;
let currentMatchId = null;
let currentToken = null;

const API_BASE = "http://localhost:8000/api/v1";
const WS_BASE = "ws://localhost:8000/ws";

// DOM Elements
const btnHost = document.getElementById('btn-host');
const btnJoin = document.getElementById('btn-join');
const inputJoinId = document.getElementById('join-match-id');
const matchIdDisplay = document.getElementById('match-id-display');
const connectionDot = document.getElementById('connection-dot');

async function hostMatch() {
    try {
        const response = await fetch(`${API_BASE}/lobby/match`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ match_settings: { game_type: "tictactoe" } })
        });
        const data = await response.json();
        currentMatchId = data.match_id;
        matchIdDisplay.innerText = `Match: ${currentMatchId}`;
        console.log("Hosted match:", currentMatchId);
        
        // Auto-join after hosting
        await joinExistingMatch(currentMatchId);
    } catch (e) {
        console.error("Failed to host match", e);
    }
}

async function joinExistingMatch(matchIdToJoin = null) {
    const matchId = matchIdToJoin || inputJoinId.value.trim();
    if (!matchId) return alert("Please enter a Match ID");
    
    try {
        const response = await fetch(`${API_BASE}/lobby/join`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ match_id: matchId, player_name: "Human_Player" })
        });
        
        if (!response.ok) throw new Error("Failed to join");
        
        const data = await response.json();
        currentToken = data.token;
        currentMatchId = matchId;
        matchIdDisplay.innerText = `Match: ${currentMatchId}`;
        
        connectWebSocket();
    } catch (e) {
        console.error("Failed to join match", e);
        alert("Failed to join match.");
    }
}

function connectWebSocket() {
    if (ws) ws.close();
    
    ws = new WebSocket(`${WS_BASE}/match/${currentMatchId}?token=${currentToken}`);
    
    ws.onopen = () => {
        connectionDot.className = "dot connected";
        console.log("WebSocket connected.");
    };
    
    ws.onclose = () => {
        connectionDot.className = "dot disconnected";
        console.log("WebSocket disconnected.");
    };
    
    ws.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            const { event_type, data } = payload;
            
            switch (event_type) {
                case 'connected':
                    console.log("Connected event:", data);
                    break;
                case 'state_update':
                    console.log("State update:", data);
                    break;
                case 'chat':
                    console.log("Chat message:", data);
                    break;
                case 'game_over':
                    console.log("Game over:", data);
                    break;
                case 'error':
                    console.error("Server error:", data);
                    break;
                default:
                    console.log("Unknown event:", payload);
            }
        } catch (e) {
            console.error("Failed to parse WS message", e);
        }
    };
}

// Bindings
btnHost.addEventListener('click', hostMatch);
btnJoin.addEventListener('click', () => joinExistingMatch());
