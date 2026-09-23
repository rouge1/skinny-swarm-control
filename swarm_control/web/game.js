"use strict";

/* Swarm Control browser client.
 * Renders the latest "state" message on a canvas and sends keyboard input over a WebSocket.
 * Add ?mock=1 to run a local fake simulation with no server. */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
var FIELD_W = 540;
var FIELD_H = 960;
var UNIT_RADIUS = 5;
var TAU = Math.PI * 2;
var FORTRESS_Y = 70;
var PLAYER_BASE_Y = 940;
var LAUNCHER_Y = 900;
var LAUNCHER_SPEED = 420;
var LAUNCHER_MARGIN = 30;
var FIRE_INTERVAL = 0.12;
var AGENT_SPEED = 260;
var BUG_SPEED = 130;
var BLUE_CAPACITY = 4000;
var RED_CAPACITY = 4000;
var SEND_HZ = 30;

// ---------------------------------------------------------------------------
// DOM and canvas
// ---------------------------------------------------------------------------
var canvas = document.getElementById("game");
var ctx = canvas.getContext("2d");
var overlay = document.getElementById("overlay");
var legend = document.getElementById("legend");

var fieldW = FIELD_W;
var fieldH = FIELD_H;

function resize() {
  var legendH = legend ? legend.offsetHeight : 24;
  var availW = window.innerWidth - 24;
  var availH = window.innerHeight - legendH - 28;
  var scale = Math.min(availW / fieldW, availH / fieldH);
  if (!(scale > 0)) scale = 1;
  var dpr = window.devicePixelRatio || 1;
  canvas.style.width = fieldW * scale + "px";
  canvas.style.height = fieldH * scale + "px";
  canvas.width = Math.max(1, Math.round(fieldW * scale * dpr));
  canvas.height = Math.max(1, Math.round(fieldH * scale * dpr));
  ctx.setTransform(scale * dpr, 0, 0, scale * dpr, 0, 0);
}

// Re-register a matchMedia listener whenever devicePixelRatio changes.
var dprQuery = null;

function onDprChange() {
  watchDpr();
  resize();
}

function watchDpr() {
  if (!window.matchMedia) return;
  var dpr = window.devicePixelRatio || 1;
  if (dprQuery) {
    if (dprQuery.removeEventListener) dprQuery.removeEventListener("change", onDprChange);
    else if (dprQuery.removeListener) dprQuery.removeListener(onDprChange);
  }
  dprQuery = window.matchMedia("(resolution: " + dpr + "dppx)");
  if (dprQuery.addEventListener) dprQuery.addEventListener("change", onDprChange);
  else if (dprQuery.addListener) dprQuery.addListener(onDprChange);
}

// ---------------------------------------------------------------------------
// Game state
// ---------------------------------------------------------------------------
var latest = null; // most recent valid "state" message
var haveState = false;
var mockMode = new URLSearchParams(window.location.search).get("mock") === "1";

var DEFAULT_STATE = {
  type: "state",
  tick: 0,
  status: "playing",
  launcher: { x: fieldW / 2, y: LAUNCHER_Y },
  blue: [],
  red: [],
  gates: [],
  bases: { enemy_hp: 100, enemy_hp_max: 100, player_hp: 100, player_hp_max: 100 },
  hud: { blue_count: 0, red_count: 0, level: 1, tokens: 0 },
};

// ---------------------------------------------------------------------------
// WebSocket connection with reconnect backoff
// ---------------------------------------------------------------------------
var socket = null;
var backoff = 500;

function connect() {
  if (mockMode) return;
  var proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  var url = proto + "//" + window.location.host + "/ws";
  try {
    socket = new WebSocket(url);
  } catch (err) {
    scheduleReconnect();
    return;
  }
  socket.onopen = function () {
    sentInput = { left: false, right: false, fire: false };
    sendInput(true);
  };
  socket.onmessage = function (ev) {
    var msg;
    try {
      msg = JSON.parse(ev.data);
    } catch (err) {
      return;
    }
    if (msg.type === "hello" && msg.field) {
      fieldW = msg.field.w;
      fieldH = msg.field.h;
      resize();
    } else if (msg.type === "state") {
      latest = msg;
      haveState = true;
      backoff = 500; // healthy connection: reset the reconnect backoff
    }
  };
  socket.onclose = function () {
    socket = null;
    haveState = false;
    scheduleReconnect();
  };
  socket.onerror = function () {
    if (socket) socket.close();
  };
}

function scheduleReconnect() {
  var delay = backoff + Math.random() * 250; // small jitter
  window.setTimeout(connect, delay);
  backoff = Math.min(backoff * 2, 10000);
}

// ---------------------------------------------------------------------------
// Keyboard input
// ---------------------------------------------------------------------------
var KEYS = new Set(["ArrowLeft", "KeyA", "ArrowRight", "KeyD", "Space"]);
var keys = { left: false, right: false, fire: false };
var sentInput = { left: false, right: false, fire: false };
var held = new Set(); // e.code values currently held

// Derive the three booleans from the set of held keys and send if changed.
function syncKeys() {
  keys.left = held.has("ArrowLeft") || held.has("KeyA");
  keys.right = held.has("ArrowRight") || held.has("KeyD");
  keys.fire = held.has("Space");
  sendInput(false);
}

function sendInput(force) {
  if (mockMode) return;
  if (
    !force &&
    keys.left === sentInput.left &&
    keys.right === sentInput.right &&
    keys.fire === sentInput.fire
  ) {
    return;
  }
  sentInput = { left: keys.left, right: keys.right, fire: keys.fire };
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(
      JSON.stringify({ type: "input", left: keys.left, right: keys.right, fire: keys.fire })
    );
  }
}

function releaseKeys() {
  held.clear();
  keys.left = false;
  keys.right = false;
  keys.fire = false;
  sendInput(true);
}

function onKeyDown(e) {
  if (e.ctrlKey || e.metaKey || e.altKey) return; // ignore shortcuts
  var code = e.code;
  if (KEYS.has(code)) e.preventDefault();
  if (e.repeat) return; // ignore auto-repeat
  if (KEYS.has(code)) {
    held.add(code);
    syncKeys();
    return;
  }
  if (code === "KeyP") {
    var st = latest ? latest.status : "playing";
    if (st === "playing") doAction("pause");
    else if (st === "paused") doAction("resume");
  } else if (code === "KeyR") {
    doAction("restart");
  }
}

function onKeyUp(e) {
  var code = e.code;
  if (KEYS.has(code)) {
    e.preventDefault();
    held.delete(code);
    syncKeys();
  }
}

function doAction(name) {
  if (mockMode) {
    if (name === "pause" && sim.status === "playing") sim.status = "paused";
    else if (name === "resume" && sim.status === "paused") sim.status = "playing";
    else if (name === "restart") resetMock();
    return;
  }
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "action", action: name }));
  }
}

// ---------------------------------------------------------------------------
// Mock simulation (?mock=1): a small local world so the client runs standalone
// ---------------------------------------------------------------------------
var MOCK_GATES = [
  { x: 110, y: 400, w: 150, h: 42, op: "mul", value: 2, label: "x2" },
  { x: 300, y: 620, w: 150, h: 42, op: "add", value: 5, label: "+5" },
];
var sim = {
  tick: 0,
  status: "playing",
  launcherX: FIELD_W / 2,
  blue: [],
  red: [],
  enemyHp: 100,
  playerHp: 100,
  fireTimer: 0,
  bugTimer: 0.5,
  level: 1,
  tokens: 0,
};

function resetMock() {
  sim.tick = 0;
  sim.status = "playing";
  sim.launcherX = fieldW / 2;
  sim.blue = [];
  sim.red = [];
  sim.enemyHp = 100;
  sim.playerHp = 100;
  sim.fireTimer = 0;
  sim.bugTimer = 0.5;
  sim.level = 1;
  sim.tokens = 0;
  latest = mockSnapshot();
  haveState = true;
}

function mockStep(dt) {
  if (sim.status !== "playing") return;
  sim.tick += 1;

  if (keys.left && !keys.right) sim.launcherX -= LAUNCHER_SPEED * dt;
  else if (keys.right && !keys.left) sim.launcherX += LAUNCHER_SPEED * dt;
  sim.launcherX = Math.max(
    LAUNCHER_MARGIN,
    Math.min(fieldW - LAUNCHER_MARGIN, sim.launcherX)
  );

  sim.fireTimer -= dt;
  if (keys.fire && sim.fireTimer <= 0 && sim.blue.length < BLUE_CAPACITY * 3) {
    sim.blue.push(sim.launcherX, LAUNCHER_Y - 20, 0);
    sim.fireTimer = FIRE_INTERVAL;
  }

  var nb = [];
  for (var i = 0; i < sim.blue.length; i += 3) {
    var by = sim.blue[i + 1] - AGENT_SPEED * dt;
    if (by > FORTRESS_Y) nb.push(sim.blue[i], by, sim.blue[i + 2]);
    else {
      sim.enemyHp = Math.max(0, sim.enemyHp - 0.4);
      sim.tokens += 1;
    }
  }
  sim.blue = nb;

  sim.bugTimer -= dt;
  if (sim.bugTimer <= 0 && sim.red.length < RED_CAPACITY * 3) {
    sim.red.push(40 + Math.random() * (fieldW - 80), FORTRESS_Y, 0);
    sim.bugTimer = 0.6 + Math.random() * 1.2;
  }

  var nr = [];
  for (var j = 0; j < sim.red.length; j += 3) {
    var ry = sim.red[j + 1] + BUG_SPEED * dt;
    if (ry < PLAYER_BASE_Y) nr.push(sim.red[j], ry, sim.red[j + 2]);
    else sim.playerHp = Math.max(0, sim.playerHp - 3);
  }
  sim.red = nr;

  if (sim.enemyHp <= 0) sim.status = "won";
  else if (sim.playerHp <= 0) sim.status = "lost";
}

// Round a packed unit list to whole field pixels for the wire format.
function roundUnits(flat) {
  var out = new Array(flat.length);
  for (var i = 0; i < flat.length; i++) out[i] = Math.round(flat[i]);
  return out;
}

function mockSnapshot() {
  return {
    type: "state",
    tick: sim.tick,
    status: sim.status,
    launcher: { x: sim.launcherX, y: LAUNCHER_Y },
    blue: roundUnits(sim.blue),
    red: roundUnits(sim.red),
    gates: MOCK_GATES,
    bases: {
      enemy_hp: sim.enemyHp,
      enemy_hp_max: 100,
      player_hp: sim.playerHp,
      player_hp_max: 100,
    },
    hud: {
      blue_count: sim.blue.length / 3,
      red_count: sim.red.length / 3,
      level: sim.level,
      tokens: sim.tokens,
    },
  };
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function drawField() {
  ctx.fillStyle = "#0b1020";
  ctx.fillRect(0, 0, fieldW, fieldH);
  ctx.strokeStyle = "rgba(255,255,255,0.05)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  var lanes = 9;
  for (var i = 1; i < lanes; i++) {
    var x = (fieldW * i) / lanes;
    ctx.moveTo(x, 0);
    ctx.lineTo(x, fieldH);
  }
  ctx.stroke();
}

function drawHpBar(x, y, w, h, ratio, color) {
  var r = Math.max(0, Math.min(1, ratio || 0));
  ctx.fillStyle = "rgba(0,0,0,0.55)";
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = color;
  ctx.fillRect(x, y, w * r, h);
  ctx.strokeStyle = "rgba(255,255,255,0.25)";
  ctx.lineWidth = 1;
  ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
}

function drawFortress(s) {
  var w = fieldW - 60;
  var h = 88;
  var x = 30;
  var top = FORTRESS_Y - h / 2;
  ctx.fillStyle = "#3a1620";
  ctx.fillRect(x, top, w, h);
  ctx.strokeStyle = "#e5484d";
  ctx.lineWidth = 2;
  ctx.strokeRect(x + 1, top + 1, w - 2, h - 2);
  ctx.fillStyle = "#ffb3b6";
  ctx.font = "bold 22px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("PRODUCTION", fieldW / 2, top + 30);
  var b = s.bases;
  drawHpBar(x + 16, top + 56, w - 32, 12, b.enemy_hp / b.enemy_hp_max, "#ff5a5f");
}

function drawBase(s) {
  ctx.fillStyle = "#12233d";
  ctx.fillRect(0, PLAYER_BASE_Y, fieldW, fieldH - PLAYER_BASE_Y);
  ctx.strokeStyle = "#4a90d9";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, PLAYER_BASE_Y);
  ctx.lineTo(fieldW, PLAYER_BASE_Y);
  ctx.stroke();
  var b = s.bases;
  drawHpBar(90, PLAYER_BASE_Y + 4, fieldW - 180, 11, b.player_hp / b.player_hp_max, "#4a90d9");
}

function drawGates(s) {
  if (!s.gates.length) return;
  ctx.font = "bold 20px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineWidth = 2;
  for (var i = 0; i < s.gates.length; i++) {
    var g = s.gates[i];
    var mul = g.op === "mul";
    ctx.fillStyle = mul ? "rgba(90,200,120,0.18)" : "rgba(240,180,70,0.18)";
    ctx.fillRect(g.x, g.y, g.w, g.h);
    ctx.strokeStyle = mul ? "#5ac878" : "#f0b446";
    ctx.strokeRect(g.x + 1, g.y + 1, g.w - 2, g.h - 2);
    ctx.fillStyle = "#eaf2ff";
    ctx.fillText(g.label, g.x + g.w / 2, g.y + g.h / 2);
  }
}

// Draw every unit of one colour in a single path: no per-unit fill or objects.
function drawUnits(flat, color) {
  if (!flat.length) return;
  ctx.fillStyle = color;
  ctx.beginPath();
  for (var i = 0; i < flat.length; i += 3) {
    var x = flat[i];
    var y = flat[i + 1];
    ctx.moveTo(x + UNIT_RADIUS, y);
    ctx.arc(x, y, UNIT_RADIUS, 0, TAU);
  }
  ctx.fill();
}

function drawLauncher(s) {
  var x = s.launcher.x;
  var y = s.launcher.y;
  ctx.fillStyle = "#4a90d9";
  ctx.beginPath();
  ctx.moveTo(x - 22, y + 14);
  ctx.lineTo(x - 13, y - 8);
  ctx.lineTo(x + 13, y - 8);
  ctx.lineTo(x + 22, y + 14);
  ctx.closePath();
  ctx.fill();
  ctx.fillRect(x - 6, y - 30, 12, 26);
  ctx.beginPath();
  ctx.arc(x, y - 4, 10, 0, TAU);
  ctx.fill();
  ctx.strokeStyle = "#bcd8ff";
  ctx.lineWidth = 2;
  ctx.stroke();
}

function drawHud(s) {
  ctx.fillStyle = "rgba(0,0,0,0.5)";
  ctx.fillRect(0, 0, fieldW, 26);
  ctx.font = "bold 14px system-ui, sans-serif";
  ctx.textBaseline = "middle";
  ctx.textAlign = "left";
  ctx.fillStyle = "#6fb3ff";
  ctx.fillText("AGENTS " + s.hud.blue_count, 12, 13);
  ctx.fillStyle = "#ff6b6b";
  ctx.fillText("BUGS " + s.hud.red_count, 150, 13);
  ctx.fillStyle = "#e8eef7";
  ctx.fillText("LV " + s.hud.level, 260, 13);
  ctx.fillStyle = "#ffd479";
  ctx.textAlign = "right";
  ctx.fillText("TOKENS " + s.hud.tokens, fieldW - 12, 13);
}

function render() {
  var s = latest || DEFAULT_STATE;
  drawField();
  drawFortress(s);
  drawBase(s);
  drawGates(s);
  drawUnits(s.blue, "#4a90ff");
  drawUnits(s.red, "#ff4d4d");
  drawLauncher(s);
  drawHud(s);
}

// ---------------------------------------------------------------------------
// Overlay (connecting / paused / won / lost)
// ---------------------------------------------------------------------------
function updateOverlay() {
  if (!overlay) return;
  if (!haveState) {
    overlay.textContent = "Connecting…";
    overlay.classList.add("show");
    return;
  }
  var st = latest ? latest.status : "playing";
  if (st === "paused") overlay.textContent = "PAUSED\nPress P to resume";
  else if (st === "won") overlay.textContent = "YOU WIN\nPress R to restart";
  else if (st === "lost") overlay.textContent = "GAME OVER\nPress R to restart";
  else {
    overlay.classList.remove("show");
    return;
  }
  overlay.classList.add("show");
}

// ---------------------------------------------------------------------------
// Main loop
// ---------------------------------------------------------------------------
var lastFrame = 0;
var lastEmit = 0;

function frame(now) {
  window.requestAnimationFrame(frame); // keep looping even if this frame throws
  if (!lastFrame) lastFrame = now;
  var dt = Math.min((now - lastFrame) / 1000, 0.1);
  lastFrame = now;

  if (mockMode) {
    mockStep(dt);
    if (now - lastEmit >= 1000 / SEND_HZ) {
      latest = mockSnapshot();
      haveState = true;
      lastEmit = now;
    }
  }

  render();
  updateOverlay();
}

// ---------------------------------------------------------------------------
// Start-up
// ---------------------------------------------------------------------------
window.addEventListener("resize", resize);
window.addEventListener("keydown", onKeyDown);
window.addEventListener("keyup", onKeyUp);
window.addEventListener("blur", releaseKeys);

resize();
watchDpr();
if (mockMode) {
  resetMock();
} else {
  connect();
}
window.requestAnimationFrame(frame);
