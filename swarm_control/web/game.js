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

var FLASH_MS = 120; // fortress bright flash after it takes damage
var SHAKE_MS = 150; // field shake after the player's base takes damage
var MOCK_WIN_SECONDS = 20; // mock mode declares a win after this long

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

// Damage feedback timers, and the HP/token baselines used for flashing and the
// win screen ("tokens now" minus "tokens at the start of the level").
var prevEnemyHp = null;
var prevPlayerHp = null;
var enemyFlashUntil = 0;
var playerFlashUntil = 0;
var prevTick = -1;
var prevLevel = -1;
var levelStartTokens = 0;

function trackDamage(s, now) {
  var b = s.bases;
  if (!b) return;
  if (prevEnemyHp !== null && b.enemy_hp < prevEnemyHp) enemyFlashUntil = now + FLASH_MS;
  if (prevPlayerHp !== null && b.player_hp < prevPlayerHp) playerFlashUntil = now + SHAKE_MS;
  prevEnemyHp = b.enemy_hp;
  prevPlayerHp = b.player_hp;
}

function trackLevel(s) {
  if (!s.hud) return;
  if (s.tick === 0 || s.hud.level !== prevLevel || (prevTick >= 0 && s.tick < prevTick)) {
    levelStartTokens = s.hud.tokens;
  }
  prevLevel = s.hud.level;
  prevTick = s.tick;
}

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
function makeMockGates() {
  return [
    { x: 55, y: 340, w: 180, h: 46, op: "mul", value: 2, label: "x2 fork", vx: 70 },
    { x: 305, y: 600, w: 180, h: 46, op: "add", value: 5, label: "+5 subagents", vx: -55 },
  ];
}

var sim = {
  tick: 0,
  time: 0,
  status: "playing",
  launcherX: FIELD_W / 2,
  blue: [],
  bluePassed: [],
  red: [],
  gates: makeMockGates(),
  enemyHp: 100,
  playerHp: 100,
  fireTimer: 0,
  bugTimer: 0.5,
  level: 1,
  tokens: 0,
};

function resetMock() {
  sim.tick = 0;
  sim.time = 0;
  sim.status = "playing";
  sim.launcherX = fieldW / 2;
  sim.blue = [];
  sim.bluePassed = [];
  sim.red = [];
  sim.gates = makeMockGates();
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
  sim.time += dt;

  if (keys.left && !keys.right) sim.launcherX -= LAUNCHER_SPEED * dt;
  else if (keys.right && !keys.left) sim.launcherX += LAUNCHER_SPEED * dt;
  sim.launcherX = Math.max(
    LAUNCHER_MARGIN,
    Math.min(fieldW - LAUNCHER_MARGIN, sim.launcherX)
  );

  sim.fireTimer -= dt;
  if (keys.fire && sim.fireTimer <= 0 && sim.blue.length < BLUE_CAPACITY * 3) {
    sim.blue.push(sim.launcherX, LAUNCHER_Y - 20, 0);
    sim.bluePassed.push(0);
    sim.fireTimer = FIRE_INTERVAL;
  }

  // Moving gates bounce off the field walls (same rule as sim/gates.py).
  for (var gi = 0; gi < sim.gates.length; gi++) {
    var g = sim.gates[gi];
    var vx = g.vx || 0;
    if (!vx) continue;
    g.x += vx * dt;
    if (g.x < 0) {
      g.x = -g.x;
      g.vx = -vx;
    } else if (g.x + g.w > fieldW) {
      g.x = 2 * (fieldW - g.w) - g.x;
      g.vx = -vx;
    }
  }

  // Agents fly up; crossing a gate once duplicates them per its op/value.
  var nb = [];
  var np = [];
  for (var i = 0; i < sim.blue.length; i += 3) {
    var ax = sim.blue[i];
    var ay = sim.blue[i + 1] - AGENT_SPEED * dt;
    var kind = sim.blue[i + 2];
    var mask = sim.bluePassed[i / 3];
    if (ay <= FORTRESS_Y) {
      sim.enemyHp = Math.max(0, sim.enemyHp - 0.6);
      sim.tokens += 1;
      continue;
    }
    for (var k = 0; k < sim.gates.length; k++) {
      var gate = sim.gates[k];
      var bit = 1 << k;
      if (
        (mask & bit) === 0 &&
        ax >= gate.x &&
        ax <= gate.x + gate.w &&
        ay >= gate.y &&
        ay <= gate.y + gate.h
      ) {
        mask |= bit;
        var copies = gate.op === "mul" ? gate.value - 1 : gate.value;
        for (var c = 0; c < copies && nb.length < BLUE_CAPACITY * 3; c++) {
          nb.push(ax + (Math.random() * 2 - 1) * 12, ay + (Math.random() * 2 - 1) * 6, kind);
          np.push(mask);
        }
      }
    }
    if (nb.length < BLUE_CAPACITY * 3) {
      nb.push(ax, ay, kind);
      np.push(mask);
    }
  }
  sim.blue = nb;
  sim.bluePassed = np;

  // Bugs walk down; reaching the player base costs HP.
  sim.bugTimer -= dt;
  if (sim.bugTimer <= 0 && sim.red.length < RED_CAPACITY * 3) {
    sim.red.push(40 + Math.random() * (fieldW - 80), FORTRESS_Y, 0);
    sim.bugTimer = 0.9 + Math.random() * 1.1;
  }

  var nr = [];
  for (var j = 0; j < sim.red.length; j += 3) {
    var ry = sim.red[j + 1] + BUG_SPEED * dt;
    if (ry < PLAYER_BASE_Y) nr.push(sim.red[j], ry, sim.red[j + 2]);
    else sim.playerHp = Math.max(0, sim.playerHp - 3);
  }
  sim.red = nr;

  if (sim.time >= MOCK_WIN_SECONDS || sim.enemyHp <= 0) sim.status = "won";
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
    gates: sim.gates,
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
  // Slightly oversized so a shake never reveals the page behind the field.
  ctx.fillRect(-12, -12, fieldW + 24, fieldH + 24);
  ctx.strokeStyle = "rgba(255,255,255,0.05)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  var lanes = 9;
  for (var i = 1; i < lanes; i++) {
    var x = (fieldW * i) / lanes;
    ctx.moveTo(x, -12);
    ctx.lineTo(x, fieldH + 12);
  }
  ctx.stroke();
}

function drawHpBar(x, y, w, h, cur, max, color) {
  var ratio = max > 0 ? cur / max : 0;
  var r = Math.max(0, Math.min(1, ratio || 0));
  ctx.fillStyle = "rgba(0,0,0,0.55)";
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = color;
  ctx.fillRect(x, y, w * r, h);
  ctx.strokeStyle = "rgba(255,255,255,0.25)";
  ctx.lineWidth = 1;
  ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
  ctx.fillStyle = "#f2f6ff";
  ctx.font = "bold 10px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(Math.round(cur) + " / " + Math.round(max), x + w / 2, y + h / 2 + 0.5);
}

function drawFortress(s, now) {
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
  ctx.fillText("PRODUCTION", fieldW / 2, top + 28);
  var b = s.bases;
  drawHpBar(x + 16, top + 52, w - 32, 16, b.enemy_hp, b.enemy_hp_max, "#ff5a5f");
  if (now < enemyFlashUntil) {
    var a = 0.15 + 0.5 * ((enemyFlashUntil - now) / FLASH_MS);
    ctx.fillStyle = "rgba(255,255,255," + a.toFixed(3) + ")";
    ctx.fillRect(x, top, w, h);
  }
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
  drawHpBar(90, PLAYER_BASE_Y + 4, fieldW - 180, 14, b.player_hp, b.player_hp_max, "#4a90d9");
}

function roundRectPath(x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// Shrink the font until the label fits inside maxW (gates can be narrow).
// The fitted size is cached by label + width so measureText runs only on change.
var gateFontCache = {};

function fitFont(text, maxW, basePx) {
  var key = text + "|" + maxW;
  var size = gateFontCache[key];
  if (size === undefined) {
    size = basePx;
    var fitted = false;
    while (size >= 8) {
      ctx.font = "bold " + size + "px system-ui, sans-serif";
      if (ctx.measureText(text).width <= maxW) {
        fitted = true;
        break;
      }
      size -= 1;
    }
    if (!fitted) size = 8;
    gateFontCache[key] = size;
  }
  ctx.font = "bold " + size + "px system-ui, sans-serif";
}

function drawGates(s) {
  if (!s.gates || !s.gates.length) return;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineWidth = 2;
  for (var i = 0; i < s.gates.length; i++) {
    var g = s.gates[i];
    var mul = g.op === "mul";
    roundRectPath(g.x, g.y, g.w, g.h, 10);
    ctx.fillStyle = mul ? "rgba(90,200,120,0.20)" : "rgba(240,180,70,0.20)";
    ctx.fill();
    ctx.strokeStyle = mul ? "#5ac878" : "#f0b446";
    ctx.stroke();
    var label = g.label == null ? "" : String(g.label);
    fitFont(label, g.w - 16, 22);
    ctx.fillStyle = mul ? "#d8ffe4" : "#fff0cf";
    ctx.fillText(label, g.x + g.w / 2, g.y + g.h / 2 + 0.5);
  }
}

// Draw every blue agent in a single path: no per-unit fill or objects.
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

// Draw every bug as a beetle in ONE path for the whole red list. Legs are only
// added below a small count: at full load the extra segments are the main cost,
// so bodies alone keep the frame budget safe.
var BUG_LEG_LIMIT = 800;

function drawBugs(flat) {
  if (!flat.length) return;
  var r = UNIT_RADIUS;
  var legs = flat.length / 3 < BUG_LEG_LIMIT;
  ctx.beginPath();
  for (var i = 0; i < flat.length; i += 3) {
    var x = flat[i];
    var y = flat[i + 1];
    ctx.moveTo(x + r, y);
    ctx.arc(x, y, r, 0, TAU);
    if (legs) {
      ctx.moveTo(x - r * 0.5, y - r * 0.4);
      ctx.lineTo(x - r * 1.5, y - r * 1.0);
      ctx.moveTo(x - r * 0.5, y + r * 0.4);
      ctx.lineTo(x - r * 1.5, y + r * 1.0);
      ctx.moveTo(x + r * 0.5, y - r * 0.4);
      ctx.lineTo(x + r * 1.5, y - r * 1.0);
      ctx.moveTo(x + r * 0.5, y + r * 0.4);
      ctx.lineTo(x + r * 1.5, y + r * 1.0);
    }
  }
  ctx.fillStyle = "#ff4d4d";
  ctx.fill();
  ctx.strokeStyle = "#ff9a9a";
  ctx.lineWidth = 1.2;
  ctx.stroke();
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

function drawDamageGlow(now) {
  if (now >= playerFlashUntil) return;
  var a = 0.5 * ((playerFlashUntil - now) / SHAKE_MS);
  ctx.strokeStyle = "rgba(255,60,60," + a.toFixed(3) + ")";
  ctx.lineWidth = 16;
  ctx.strokeRect(8, 8, fieldW - 16, fieldH - 16);
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

function render(now) {
  var s = latest || DEFAULT_STATE;
  var dx = 0;
  var dy = 0;
  if (now < playerFlashUntil) {
    var t = (playerFlashUntil - now) / SHAKE_MS;
    dx = (Math.random() * 2 - 1) * 5 * t;
    dy = (Math.random() * 2 - 1) * 3 * t;
  }
  ctx.save();
  ctx.translate(dx, dy);
  drawField();
  drawFortress(s, now);
  drawBase(s);
  drawGates(s);
  drawUnits(s.blue, "#4a90ff");
  drawBugs(s.red);
  drawLauncher(s);
  ctx.restore();
  drawDamageGlow(now);
  drawHud(s);
}

// ---------------------------------------------------------------------------
// Overlay (connecting / paused / won / lost)
// ---------------------------------------------------------------------------
var overlayKey = null;

function updateOverlay() {
  if (!overlay) return;
  var key;
  if (!haveState) key = "connecting";
  else key = latest ? latest.status : "playing";
  if (key === overlayKey) return;
  overlayKey = key;

  overlay.classList.remove("won", "lose");
  if (key === "connecting") {
    overlay.textContent = "Connecting…";
    overlay.classList.add("show");
  } else if (key === "paused") {
    overlay.textContent = "PAUSED\nPress P to resume";
    overlay.classList.add("show");
  } else if (key === "won") {
    var gained = latest ? Math.max(0, latest.hud.tokens - levelStartTokens) : 0;
    overlay.innerHTML =
      '<div class="end">' +
      '<div class="end-title">SHIPPED!</div>' +
      '<div class="end-line">Production is bug-free</div>' +
      '<div class="end-tokens">+' + gained + " tokens</div>" +
      '<div class="end-hint">Press R to play again</div>' +
      "</div>";
    overlay.classList.add("show", "won");
  } else if (key === "lost") {
    overlay.innerHTML =
      '<div class="end">' +
      '<div class="end-title">OUTAGE</div>' +
      '<div class="end-line">Bugs reached your base</div>' +
      '<div class="end-hint">Press R to try again</div>' +
      "</div>";
    overlay.classList.add("show", "lose");
  } else {
    overlay.classList.remove("show");
  }
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

  try {
    if (mockMode) {
      mockStep(dt);
      if (now - lastEmit >= 1000 / SEND_HZ) {
        latest = mockSnapshot();
        haveState = true;
        lastEmit = now;
      }
    }
    if (haveState && latest) {
      trackLevel(latest);
      trackDamage(latest, now);
    }
    render(now);
    updateOverlay();
  } catch (err) {
    // A malformed state must never stop the animation loop.
    overlayKey = null;
  }
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
