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

let currentMatchId = null;
let myToken = null;
let myPlayerName = null;

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
    console.log('Auth token acquired for match', currentMatchId);
}

els.hostBtn.addEventListener('click', hostMatch);
els.joinBtn.addEventListener('click', joinExistingMatch);
