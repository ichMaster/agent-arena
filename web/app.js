'use strict';
/* AgentArena Web UI — one WebSocket + the routeEvent dispatcher (web_ui_spec §6-8, architecture §8).
   A stateless renderer: it holds no authoritative game state; every visible change comes from a
   server event, and it sends back only the actions its role permits. v03.01 wires the lobby +
   connection + the dispatcher skeleton; board rendering is v03.02, chat + observer is v03.03. */

// --- Minimal, transient, non-authoritative client state (web_ui_spec §7) ---
let ws = null;
let currentMatchId = null;
let myToken = null;
let myPlayerName = null;
let mySymbol = null;          // "X" / "O" / null — set only from the server's joined event
let isGameActive = false;     // false after game_over; gates interactivity

const byId = (id) => document.getElementById(id);
const apiBase = () => window.location.origin;
const wsBase = () => apiBase().replace(/^http/, 'ws');

function setConnectionStatus(state, resultText) {
  const dot = byId('status-dot');
  const label = byId('status-label');
  if (dot) dot.dataset.state = state;
  if (!label) return;
  if (state === 'connected') label.textContent = 'Connected';
  else if (state === 'over') label.textContent = 'Game Over — ' + (resultText || '');
  else label.textContent = 'Disconnected';
}

// The Match ID is shown IN FULL — never truncated. It is the exact string a user copies into
// `agent/agent.py --match-id …`; a shortened display would silently hand out an id that 404s.
function setMatchIdDisplay(id) {
  const el = byId('match-id');
  if (!el) return;
  el.textContent = id;
  el.title = id;
}

async function postJSON(path, body) {
  const resp = await fetch(apiBase() + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : null,
  });
  if (!resp.ok) throw new Error('request failed: ' + resp.status);
  return resp.json();
}

const defaultName = () => 'Human-' + Math.floor(Math.random() * 10000);

// --- Lobby flows (web_ui_spec §8) ---
async function hostMatch() {
  const created = await postJSON('/api/v1/lobby/match', null);
  await joinAndConnect(created.match_id, false);
}

async function joinMatch() {
  const id = (window.prompt('Match ID to join:') || '').trim();
  if (id) await joinAndConnect(id, false);
}

async function spectateMatch() {
  const id = (window.prompt('Match ID to observe:') || '').trim();
  if (id) await joinAndConnect(id, true);
}

async function joinAndConnect(matchId, spectator) {
  myPlayerName = myPlayerName || defaultName();
  const joined = await postJSON('/api/v1/lobby/join', {
    match_id: matchId, player_name: myPlayerName, spectator: spectator,
  });
  currentMatchId = matchId;
  myToken = joined.token;
  mySymbol = null;
  isGameActive = true;   // reset on EVERY new connection (§7 — else a 2nd match in-tab stays frozen)
  resetPlayState();
  setMatchIdDisplay(matchId);
  openSocket(matchId, joined.token);
}

// Clear the board + banner when (re)connecting, so a second match in the same tab starts fresh (§7).
function resetPlayState() {
  for (let i = 0; i < 9; i++) {
    const cell = byId('cell-' + i);
    if (cell) { cell.textContent = ''; cell.className = 'cell empty'; cell.disabled = true; }
  }
  const banner = byId('turn-banner');
  if (banner) banner.textContent = 'Connecting…';
}

function openSocket(matchId, token) {
  if (ws) { try { ws.close(); } catch (e) { /* ignore */ } }
  ws = new WebSocket(wsBase() + '/ws/match/' + matchId + '?token=' + token);
  ws.addEventListener('open', () => setConnectionStatus('connected'));
  ws.addEventListener('message', (ev) => routeEvent(JSON.parse(ev.data)));
  ws.addEventListener('close', () => { if (isGameActive) setConnectionStatus('disconnected'); });
}

// Guard every send: only when the socket is OPEN (web_ui_spec §6.3).
function sendAction(action, payload) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ action: action, payload: payload }));
}

// --- Rendering (web_ui_spec §4.2-4.3, §6). Every pixel derives from a server event. ---

// The 8 winning lines — used only to highlight the win presentationally (game_over carries just
// `result`, not the line; the server remains the sole authority on the outcome, §6).
const WIN_LINES = [
  [0, 1, 2], [3, 4, 5], [6, 7, 8],
  [0, 3, 6], [1, 4, 7], [2, 5, 8],
  [0, 4, 8], [2, 4, 6],
];

// "Your turn" is derived, not pushed (§6.2): a cell is playable only when it's empty, the game is
// active, it's my turn, and the move is in valid_moves. current_turn is null on the ending move.
function renderBoard(board, currentTurn, validMoves) {
  const legal = new Set(validMoves || []);
  const myTurn = isGameActive && mySymbol !== null && currentTurn === mySymbol;
  for (let i = 0; i < 9; i++) {
    const cell = byId('cell-' + i);
    if (!cell) continue;
    const mark = board && board[i] ? board[i] : '';
    cell.textContent = mark;
    cell.classList.remove('x', 'o', 'empty', 'playable', 'win');
    if (mark === 'X') cell.classList.add('x');
    else if (mark === 'O') cell.classList.add('o');
    else cell.classList.add('empty');
    const playable = mark === '' && myTurn && legal.has(i);
    cell.classList.toggle('playable', playable);
    cell.disabled = !playable;   // the real <button> disabled attribute (a11y §9), not just a class
  }
}

// Two cards; the one whose symbol equals current_turn is .active (neither when current_turn is null).
// Null-safe for the Observer (mySymbol === null) — never calls null.toLowerCase() (§5).
function renderPlayers(currentTurn) {
  ['X', 'O'].forEach((sym) => {
    const card = byId('card-' + sym.toLowerCase());
    const name = byId('name-' + sym.toLowerCase());
    const role = byId('role-' + sym.toLowerCase());
    const isMe = mySymbol !== null && sym === mySymbol;
    if (name) name.textContent = isMe ? 'You' : ('Player ' + sym);
    if (role) role.textContent = isMe ? 'Human · Player' : 'Haiku · Agent';
    if (card) card.classList.toggle('active', currentTurn === sym);
  });
}

function renderTurnBanner(currentTurn) {
  const banner = byId('turn-banner');
  if (!banner) return;
  if (!isGameActive) { banner.textContent = 'Game over'; return; }
  if (mySymbol === null) {
    banner.textContent = currentTurn ? ('Observing — ' + currentTurn + ' to move') : 'Observing';
    return;
  }
  if (currentTurn === mySymbol) banner.innerHTML = "It's <b>your</b> turn — pick a square";
  else banner.textContent = 'Waiting for the opponent…';
}

// --- The single dispatcher (web_ui_spec §6.1). One case per server event. ---
// Board rendering (state_update) lands in v03.02; chat (chat_message) in v03.03.
function routeEvent(message) {
  const event = message.event;
  const payload = message.payload || {};
  switch (event) {
    case 'joined':
      mySymbol = payload.symbol;               // server-decided role: "X"/"O"/null (Observer)
      setConnectionStatus('connected');
      renderPlayers(payload.current_turn);
      renderBoard(payload.board, payload.current_turn, payload.valid_moves);
      renderTurnBanner(payload.current_turn);
      break;
    case 'state_update':
      renderBoard(payload.board, payload.current_turn, payload.valid_moves);
      renderPlayers(payload.current_turn);
      renderTurnBanner(payload.current_turn);
      break;
    case 'chat_message':
      break;
    case 'game_over':
      isGameActive = false;
      setConnectionStatus('over', payload.result);
      break;
    case 'error':
      console.warn('server error:', payload.detail);
      break;
    default:
      break;
  }
}

function wireUI() {
  const host = byId('btn-host');
  const join = byId('btn-join');
  const observe = byId('btn-observe');
  if (host) host.addEventListener('click', () => hostMatch().catch((e) => console.error(e)));
  if (join) join.addEventListener('click', () => joinMatch().catch((e) => console.error(e)));
  if (observe) observe.addEventListener('click', () => spectateMatch().catch((e) => console.error(e)));
}

if (typeof document !== 'undefined') {
  if (document.readyState !== 'loading') wireUI();
  else document.addEventListener('DOMContentLoaded', wireUI);
}

// Expose the entry points so the served-asset tests can assert them without a DOM.
if (typeof window !== 'undefined') {
  window.arena = {
    hostMatch, joinMatch, spectateMatch, joinAndConnect,
    routeEvent, sendAction, setConnectionStatus, setMatchIdDisplay,
    renderBoard, renderPlayers, resetPlayState,
  };
}
