const els = {
    dot: document.getElementById('connection-dot'),
    statusText: document.getElementById('connection-text'),
    matchIdDisplay: document.getElementById('match-id-display'),
    board: document.getElementById('board'),
    log: document.getElementById('log'),
    chatForm: document.getElementById('chat-form'),
    chatInput: document.getElementById('chat-input'),
    sendBtn: document.getElementById('sendBtn'),
    hostBtn: document.getElementById('host-match-btn'),
    joinBtn: document.getElementById('join-match-btn'),
};

let ws = null;
let currentMatchId = null;
let myToken = null;
let myPlayerName = null;
let mySymbol = null;
let isGameActive = true;

async function hostMatch() {
    const response = await fetch('/api/v1/lobby/match', { method: 'POST' });
    const data = await response.json();
    currentMatchId = data.match_id;
    els.matchIdDisplay.textContent = `• Match #${currentMatchId.slice(0, 8)}`;
    await promptAndJoin();
}

async function joinExistingMatch() {
    const matchId = window.prompt('Enter the Match ID to join:');
    if (!matchId) return;
    currentMatchId = matchId.trim();
    els.matchIdDisplay.textContent = `• Match #${currentMatchId.slice(0, 8)}`;
    await promptAndJoin();
}

async function promptAndJoin() {
    myPlayerName = window.prompt('Enter your name:', 'Human') || 'Human';
    const response = await fetch('/api/v1/lobby/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ match_id: currentMatchId, player_name: myPlayerName }),
    });
    if (!response.ok) {
        console.error('Failed to join match:', response.status);
        return;
    }
    const data = await response.json();
    myToken = data.token;
    connectSocket();
}

function connectSocket() {
    const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${wsScheme}://${window.location.host}/ws/match/${currentMatchId}?token=${myToken}`;
    ws = new WebSocket(url);

    ws.onopen = () => {
        els.dot.classList.add('connected');
        els.statusText.textContent = 'Connected';
    };
    ws.onclose = () => {
        els.dot.classList.remove('connected');
        els.statusText.textContent = 'Disconnected';
    };
    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        routeEvent(data);
    };
}

function routeEvent({ event, payload }) {
    switch (event) {
        case 'joined':
            mySymbol = payload.symbol;
            initPlayerCards(mySymbol);
            renderBoard(payload.board, payload.current_turn, payload.valid_moves);
            break;
        case 'state_update':
            renderBoard(payload.board, payload.current_turn, payload.valid_moves);
            break;
        case 'chat_message':
        case 'game_over':
        case 'error':
            // Wired up in v04.03/ARENA-031.
            console.log(`[${event}]`, payload);
            break;
        default:
            console.warn('Unknown event type:', event, payload);
    }
}

function initPlayerCards(symbol) {
    const otherSymbol = symbol === 'X' ? 'O' : 'X';
    const humanSymbolEl = document.querySelector('#player-card-human .player-symbol');
    const agentSymbolEl = document.querySelector('#player-card-agent .player-symbol');
    humanSymbolEl.textContent = symbol;
    humanSymbolEl.className = `player-symbol player-symbol-${symbol.toLowerCase()}`;
    agentSymbolEl.textContent = otherSymbol;
    agentSymbolEl.className = `player-symbol player-symbol-${otherSymbol.toLowerCase()}`;
}

function renderBoard(board, currentTurn, validMoves) {
    board.forEach((mark, index) => {
        const cell = document.getElementById(`cell-${index}`);
        cell.textContent = mark || '';
        cell.classList.remove('x', 'o');
        if (mark === 'X' || mark === 'O') cell.classList.add(mark.toLowerCase());
    });

    const isMyTurn = isGameActive && currentTurn === mySymbol;
    document.getElementById('player-card-human').classList.toggle('active', currentTurn === mySymbol);
    document.getElementById('player-card-agent').classList.toggle('active', currentTurn !== mySymbol);

    board.forEach((mark, index) => {
        const cell = document.getElementById(`cell-${index}`);
        const isValid = !validMoves || validMoves.includes(index);
        cell.classList.toggle('disabled', !(isMyTurn && !mark && isValid));
    });
}

function handleCellClick(index) {
    if (!ws || ws.readyState !== WebSocket.OPEN || !isGameActive) return;
    const cell = document.getElementById(`cell-${index}`);
    if (cell.classList.contains('disabled')) return;
    ws.send(JSON.stringify({ action: 'submit_move', payload: { move: index } }));
}

for (let i = 0; i < 9; i++) {
    document.getElementById(`cell-${i}`).addEventListener('click', () => handleCellClick(i));
}

els.hostBtn.addEventListener('click', hostMatch);
els.joinBtn.addEventListener('click', joinExistingMatch);
