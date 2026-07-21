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
  setMatchIdDisplay(matchId);
  openSocket(matchId, joined.token);
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

// --- The single dispatcher (web_ui_spec §6.1). One case per server event. ---
// Board rendering (state_update) lands in v03.02; chat (chat_message) in v03.03.
function routeEvent(message) {
  const event = message.event;
  const payload = message.payload || {};
  switch (event) {
    case 'joined':
      mySymbol = payload.symbol;               // server-decided role: "X"/"O"/null (Observer)
      setConnectionStatus('connected');
      break;
    case 'state_update':
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
  };
}
