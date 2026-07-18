let ws = null;
let currentMatchId = null;
let currentToken = null;
let mySymbol = null;
let currentTurn = "X";
let gameOver = false;

const API_BASE = "http://localhost:8000/api/v1";
const WS_BASE = "ws://localhost:8000/ws";

// DOM Elements
const btnHost = document.getElementById('btn-host');
const btnJoin = document.getElementById('btn-join');
const inputJoinId = document.getElementById('join-match-id');
const matchIdDisplay = document.getElementById('match-id-display');
const connectionDot = document.getElementById('connection-dot');
const cells = document.querySelectorAll('.cell');
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const btnSendChat = document.getElementById('btn-send-chat');
const playerCards = document.querySelectorAll('.player-card');

function renderBoard(board) {
    cells.forEach((cell, index) => {
        const value = board[index];
        cell.innerHTML = '';
        if (value) {
            const span = document.createElement('span');
            span.className = `symbol-${value.toLowerCase()}`;
            span.innerText = value;
            cell.appendChild(span);
        }
    });
}

function updateTurnUI() {
    playerCards.forEach(card => card.classList.remove('active-turn'));
    if (currentTurn === "X") {
        playerCards[0].classList.add('active-turn');
    } else if (currentTurn === "O") {
        playerCards[1].classList.add('active-turn');
    }
}

function renderChat(messageData, senderClass) {
    const div = document.createElement('div');
    div.className = `message ${senderClass}`;
    div.innerHTML = messageData;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

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
        chatInput.disabled = false;
        btnSendChat.disabled = false;
        renderChat("Connected to server.", "system-msg");
        gameOver = false;
    };
    
    ws.onclose = () => {
        connectionDot.className = "dot disconnected";
        console.log("WebSocket disconnected.");
        chatInput.disabled = true;
        btnSendChat.disabled = true;
    };
    
    ws.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            const { event_type, data } = payload;
            
            switch (event_type) {
                case 'connected':
                    mySymbol = data.symbol;
                    renderChat(`Assigned symbol: ${mySymbol}`, "system-msg");
                    renderBoard(data.state.board);
                    currentTurn = data.state.current_turn;
                    updateTurnUI();
                    break;
                case 'state_update':
                    renderBoard(data.board);
                    currentTurn = data.current_turn;
                    updateTurnUI();
                    break;
                case 'chat':
                    renderChat(`<strong>User/Agent:</strong> ${data.message || data}`, "agent-msg");
                    break;
                case 'game_over':
                    gameOver = true;
                    renderChat(`GAME OVER! Winner: ${data.winner}`, "system-msg");
                    matchIdDisplay.innerText += ` (Winner: ${data.winner})`;
                    break;
                case 'error':
                    renderChat(`Error: ${data.message}`, "system-msg");
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

cells.forEach(cell => {
    cell.addEventListener('click', () => {
        if (gameOver || currentTurn !== mySymbol) return;
        const index = parseInt(cell.dataset.index);
        if (ws) {
            ws.send(JSON.stringify({
                action: 'submit_move',
                payload: { move: index }
            }));
        }
    });
});

btnSendChat.addEventListener('click', () => {
    const msg = chatInput.value.trim();
    if (msg && ws) {
        ws.send(JSON.stringify({
            action: 'chat',
            payload: { message: msg }
        }));
        chatInput.value = '';
    }
});

chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') btnSendChat.click();
});
