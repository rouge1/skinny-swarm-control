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
var PLAYER_FLASH_MS = 150; // player base flash after a bug reaches it
var SHAKE_MS = 150; // field shake after the player's base takes damage

// --- phase 5: juice
var GATE_NEAR_MIN = 1; // agents entering a gate box that counts as a gate event
var GATE_BURST_COOLDOWN = 180; // ms between bursts on the same gate
var PARTICLE_MAX = 160; // fixed pool: bursts never allocate unboundedly
var PARTICLE_GRAVITY = 320; // px/s^2 pulling sparks down

// --- phase 4: campaign upgrades (mirrors swarm_control/config.py)
var FIRE_RATE_FACTOR = 0.85;
var LAUNCHER_SPEED_FACTOR = 1.25;
var MULTISHOT_SPACING = 12;

// Shop catalogue shared by the overlay and the mock.
var UPGRADES = [
  { key: "fire_rate", num: "1", label: "FIRE RATE", max: 4 },
  { key: "multishot", num: "2", label: "MULTISHOT", max: 2 },
  { key: "speed", num: "3", label: "SPEED", max: 3 },
];

// Mock campaign: three levels so the shop can be tried with no server.
var MOCK_LEVELS = [
  { name: "First Contact", enemyHp: 100, playerHp: 100, seconds: 20, reward: 10 },
  { name: "Parallel Front", enemyHp: 140, playerHp: 100, seconds: 25, reward: 25 },
  { name: "Swarm Cascade", enemyHp: 180, playerHp: 100, seconds: 30, reward: 50 },
];
var MOCK_PRICES = {
  fire_rate: [20, 40, 80, 160],
  multishot: [30, 90],
  speed: [15, 30, 60],
};

// ---------------------------------------------------------------------------
// DOM and canvas
// ---------------------------------------------------------------------------
var canvas = document.getElementById("game");
var ctx = canvas.getContext("2d");
var overlay = document.getElementById("overlay");
var menu = document.getElementById("menu");
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

// Phase 5 screens and juice. The title is up until Space is pressed, the help
// overlay can cover the game at any time, and "M" toggles every juice effect.
var started = false;
var helpOpen = false;
var motion = true;
var resumePending = false; // hiding PAUSED while the start-of-game resume is in flight

var DEFAULT_STATE = {
  type: "state",
  tick: 0,
  status: "playing",
  launcher: { x: fieldW / 2, y: LAUNCHER_Y },
  blue: [],
  red: [],
  gates: [],
  bases: { enemy_hp: 100, enemy_hp_max: 100, player_hp: 100, player_hp_max: 100 },
  hud: {
    blue_count: 0,
    red_count: 0,
    level: 1,
    tokens: 0,
    has_next: true,
    upgrades: { fire_rate: 0, multishot: 0, speed: 0 },
    prices: { fire_rate: 20, multishot: 30, speed: 15 },
    level_name: "Sandbox",
  },
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
  if (motion && prevEnemyHp !== null && b.enemy_hp < prevEnemyHp) enemyFlashUntil = now + FLASH_MS;
  if (motion && prevPlayerHp !== null && b.player_hp < prevPlayerHp) {
    playerFlashUntil = now + PLAYER_FLASH_MS;
  }
  prevEnemyHp = b.enemy_hp; // always updated so re-enabling motion cannot flash stale damage
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

// Re-seed every feedback baseline from the newest snapshot. Called when the
// title is dismissed so the first live frame cannot flash damage or burst at a
// gate that was crossed before play began.
function resetTracking(s) {
  prevEnemyHp = null;
  prevPlayerHp = null;
  enemyFlashUntil = 0;
  playerFlashUntil = 0;
  prevTick = -1;
  prevLevel = -1;
  gateInit = false;
  if (!s) return;
  if (s.bases) {
    prevEnemyHp = s.bases.enemy_hp;
    prevPlayerHp = s.bases.player_hp;
  }
  if (s.hud) {
    prevLevel = s.hud.level;
    prevTick = s.tick;
    levelStartTokens = s.hud.tokens;
  }
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
    // The world starts stepping the moment the socket opens. Keep it paused
    // behind the title so play begins on frame one instead of mid-level.
    if (!started && socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "action", action: "pause" }));
    }
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

  // Help toggles at any time, including from the title screen.
  if (code === "KeyH" || code === "Slash") {
    e.preventDefault();
    if (e.repeat) return;
    setHelp(!helpOpen);
    return;
  }
  if (helpOpen) {
    if (code === "Escape") {
      e.preventDefault();
      setHelp(false);
    }
    return; // help is modal: swallow movement, fire and actions while it is open
  }
  if (code === "KeyM") {
    if (e.repeat) return;
    motion = !motion;
    if (!motion) clearParticles();
    return;
  }
  if (!started) {
    if (code === "Space") {
      e.preventDefault();
      startGame();
    }
    return; // nothing else happens before the title is dismissed
  }

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
  } else if (code === "KeyN") {
    if (latest && latest.status === "won" && latest.hud && latest.hud.has_next) {
      doAction("next");
    }
  } else if (code === "Digit1" || code === "Numpad1") {
    shopBuy("fire_rate");
  } else if (code === "Digit2" || code === "Numpad2") {
    shopBuy("multishot");
  } else if (code === "Digit3" || code === "Numpad3") {
    shopBuy("speed");
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

function startGame() {
  started = true;
  menuKey = null; // hide the title
  resetTracking(latest); // fresh baselines for the first live frame
  if (mockMode) return; // the local sim unfreezes on its own
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "action", action: "resume" }));
  }
  resumePending = true; // do not flash PAUSED while the resume is in flight
  overlayKey = null;
}

function setHelp(open) {
  if (open === helpOpen) return;
  helpOpen = open;
  if (open) releaseKeys(); // never leave a key stuck while the modal is up
  menuKey = null;
}

function doAction(name) {
  if (mockMode) {
    if (name === "pause" && sim.status === "playing") sim.status = "paused";
    else if (name === "resume" && sim.status === "paused") sim.status = "playing";
    else if (name === "restart") resetMock();
    else if (name === "next") mockNext();
    else if (name.indexOf("buy_") === 0) mockBuy(name.slice(4));
    return;
  }
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "action", action: name }));
  }
}

// Buy the named upgrade from the shop only when it is affordable and not maxed.
function shopBuy(kind) {
  if (!latest || latest.status !== "won") return;
  var hud = latest.hud || {};
  if (!hud.has_next || !hud.upgrades || !hud.prices) return;
  var level = hud.upgrades[kind] || 0;
  var price = hud.prices[kind];
  if (price === null || price === undefined || hud.tokens < price) return;
  for (var i = 0; i < UPGRADES.length; i++) {
    if (UPGRADES[i].key === kind && level < UPGRADES[i].max) doAction("buy_" + kind);
  }
}

function mockNext() {
  if (sim.status !== "won" || sim.level >= MOCK_LEVELS.length) return;
  sim.level += 1;
  startMockLevel();
  latest = mockSnapshot();
  haveState = true;
}

function mockBuy(kind) {
  if (sim.status !== "won") return;
  var prices = MOCK_PRICES[kind];
  var level = sim.upgrades[kind];
  if (!prices || level >= prices.length) return;
  var price = prices[level];
  if (sim.tokens < price) return;
  sim.tokens -= price;
  sim.upgrades[kind] = level + 1;
  latest = mockSnapshot();
  haveState = true;
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
  upgrades: { fire_rate: 0, multishot: 0, speed: 0 },
};

function startMockLevel() {
  var data = MOCK_LEVELS[sim.level - 1] || MOCK_LEVELS[0];
  sim.tick = 0;
  sim.time = 0;
  sim.status = "playing";
  sim.launcherX = fieldW / 2;
  sim.blue = [];
  sim.bluePassed = [];
  sim.red = [];
  sim.gates = makeMockGates();
  sim.enemyHp = data.enemyHp;
  sim.playerHp = data.playerHp;
  sim.fireTimer = 0;
  sim.bugTimer = 0.5;
}

function resetMock() {
  startMockLevel();
  latest = mockSnapshot();
  haveState = true;
}

function mockStep(dt) {
  if (sim.status !== "playing") return;
  sim.tick += 1;
  sim.time += dt;

  var speed = LAUNCHER_SPEED * Math.pow(LAUNCHER_SPEED_FACTOR, sim.upgrades.speed);
  if (keys.left && !keys.right) sim.launcherX -= speed * dt;
  else if (keys.right && !keys.left) sim.launcherX += speed * dt;
  sim.launcherX = Math.max(
    LAUNCHER_MARGIN,
    Math.min(fieldW - LAUNCHER_MARGIN, sim.launcherX)
  );

  sim.fireTimer -= dt;
  var shots = 1 + sim.upgrades.multishot;
  var fireInterval = FIRE_INTERVAL * Math.pow(FIRE_RATE_FACTOR, sim.upgrades.fire_rate);
  if (keys.fire && sim.fireTimer <= 0 && sim.blue.length < BLUE_CAPACITY * 3) {
    for (var sh = 0; sh < shots && sim.blue.length < BLUE_CAPACITY * 3; sh++) {
      var off = (sh - (shots - 1) / 2) * MULTISHOT_SPACING;
      sim.blue.push(sim.launcherX + off, LAUNCHER_Y - 20, 0);
      sim.bluePassed.push(0);
    }
    sim.fireTimer = fireInterval;
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

  var data = MOCK_LEVELS[sim.level - 1] || MOCK_LEVELS[0];
  if (sim.time >= data.seconds || sim.enemyHp <= 0) {
    sim.status = "won";
    sim.tokens += data.reward;
  } else if (sim.playerHp <= 0) {
    sim.status = "lost";
  }
}

// Round a packed unit list to whole field pixels for the wire format.
function roundUnits(flat) {
  var out = new Array(flat.length);
  for (var i = 0; i < flat.length; i++) out[i] = Math.round(flat[i]);
  return out;
}

function mockPrice(kind) {
  var prices = MOCK_PRICES[kind];
  var level = sim.upgrades[kind];
  return level < prices.length ? prices[level] : null;
}

function mockSnapshot() {
  var data = MOCK_LEVELS[sim.level - 1] || MOCK_LEVELS[0];
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
      enemy_hp_max: data.enemyHp,
      player_hp: sim.playerHp,
      player_hp_max: data.playerHp,
    },
    hud: {
      blue_count: sim.blue.length / 3,
      red_count: sim.red.length / 3,
      level: sim.level,
      tokens: sim.tokens,
      has_next: sim.level < MOCK_LEVELS.length,
      upgrades: {
        fire_rate: sim.upgrades.fire_rate,
        multishot: sim.upgrades.multishot,
        speed: sim.upgrades.speed,
      },
      prices: {
        fire_rate: mockPrice("fire_rate"),
        multishot: mockPrice("multishot"),
        speed: mockPrice("speed"),
      },
      level_name: data.name,
    },
  };
}

// ---------------------------------------------------------------------------
// Juice: particle bursts, gate events, motion toggle (M)
// ---------------------------------------------------------------------------
// A fixed pool of particle objects; bursts cycle through it so the loop never
// allocates during play. A particle with life <= 0 is inactive.
var particles = [];
for (var pi = 0; pi < PARTICLE_MAX; pi++) {
  particles.push({ x: 0, y: 0, vx: 0, vy: 0, life: 0, max: 1, size: 2, color: "#fff" });
}
var particleHead = 0;

function clearParticles() {
  for (var i = 0; i < PARTICLE_MAX; i++) particles[i].life = 0;
}

function spawnBurst(x, y, op) {
  if (!motion) return;
  var color = op === "mul" ? "#7dffb0" : "#ffcf6b";
  for (var i = 0; i < 12; i++) {
    var p = particles[particleHead];
    particleHead = (particleHead + 1) % PARTICLE_MAX;
    var a = Math.random() * TAU;
    var sp = 40 + Math.random() * 110;
    p.x = x + (Math.random() * 2 - 1) * 8;
    p.y = y + (Math.random() * 2 - 1) * 8;
    p.vx = Math.cos(a) * sp;
    p.vy = Math.sin(a) * sp - 30;
    p.max = 0.28 + Math.random() * 0.24;
    p.life = p.max;
    p.size = 2 + Math.random() * 2.5;
    p.color = color;
  }
}

function updateParticles(dt) {
  for (var i = 0; i < PARTICLE_MAX; i++) {
    var p = particles[i];
    if (p.life <= 0) continue;
    p.life -= dt;
    if (p.life <= 0) continue;
    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.vy += PARTICLE_GRAVITY * dt;
    p.vx *= 0.98;
  }
}

function drawParticles() {
  for (var i = 0; i < PARTICLE_MAX; i++) {
    var p = particles[i];
    if (p.life <= 0) continue;
    ctx.globalAlpha = Math.min(1, p.life / p.max);
    ctx.fillStyle = p.color;
    ctx.fillRect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size);
  }
  ctx.globalAlpha = 1;
}

// The client never sees a gate "fired" message, so count how many agents sit
// inside each gate box. When that count rises, agents entered (and therefore
// multiplied) there: burst at that gate. A per-gate cooldown keeps it cheap.
var gateTick = -1;
var gateLevel = -1;
var gateInit = false;
var gateNear = [];
var gateLastBurst = [];

function countInGate(g, blue) {
  var n = 0;
  for (var j = 0; j < blue.length; j += 3) {
    var x = blue[j];
    var y = blue[j + 1];
    if (x >= g.x - 8 && x <= g.x + g.w + 8 && y >= g.y - 8 && y <= g.y + g.h + 8) n += 1;
  }
  return n;
}

function trackGates(s, now) {
  var gates = s.gates;
  if (!gates || !gates.length) {
    gateInit = false;
    return;
  }
  if (s.hud && s.hud.level !== gateLevel) {
    gateLevel = s.hud.level;
    gateInit = false;
  }
  if (s.tick === gateTick && gateInit) return;
  gateTick = s.tick;
  var blue = s.blue || [];
  var i;
  if (!gateInit || gateNear.length !== gates.length) {
    gateNear = new Array(gates.length);
    for (i = 0; i < gates.length; i++) gateNear[i] = countInGate(gates[i], blue);
    gateInit = true;
    return;
  }
  var active = motion && started && !helpOpen && s.status === "playing";
  for (i = 0; i < gates.length; i++) {
    var near = countInGate(gates[i], blue);
    var inc = near - (gateNear[i] || 0);
    gateNear[i] = near;
    if (inc >= GATE_NEAR_MIN && active && now - (gateLastBurst[i] || -1e9) >= GATE_BURST_COOLDOWN) {
      gateLastBurst[i] = now;
      spawnBurst(gates[i].x + gates[i].w / 2, gates[i].y + gates[i].h / 2, gates[i].op);
    }
  }
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
  if (motion && now < enemyFlashUntil) {
    var a = 0.15 + 0.5 * ((enemyFlashUntil - now) / FLASH_MS);
    ctx.fillStyle = "rgba(255,255,255," + a.toFixed(3) + ")";
    ctx.fillRect(x, top, w, h);
  }
}

function drawBase(s, now) {
  ctx.fillStyle = "#12233d";
  ctx.fillRect(0, PLAYER_BASE_Y, fieldW, fieldH - PLAYER_BASE_Y);
  if (motion && now < playerFlashUntil) {
    var fa = 0.5 * ((playerFlashUntil - now) / PLAYER_FLASH_MS);
    ctx.fillStyle = "rgba(255,70,70," + fa.toFixed(3) + ")";
    ctx.fillRect(0, PLAYER_BASE_Y, fieldW, fieldH - PLAYER_BASE_Y);
  }
  ctx.strokeStyle = "#4a90d9";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, PLAYER_BASE_Y);
  ctx.lineTo(fieldW, PLAYER_BASE_Y);
  ctx.stroke();
  var b = s.bases;
  drawHpBar(170, PLAYER_BASE_Y + 4, 200, 14, b.player_hp, b.player_hp_max, "#4a90d9");
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
  if (!motion || now >= playerFlashUntil) return;
  var a = 0.5 * ((playerFlashUntil - now) / PLAYER_FLASH_MS);
  ctx.strokeStyle = "rgba(255,60,60," + a.toFixed(3) + ")";
  ctx.lineWidth = 16;
  ctx.strokeRect(8, 8, fieldW - 16, fieldH - 16);
}

function drawHud(s) {
  var hud = s.hud || {};
  ctx.fillStyle = "rgba(0,0,0,0.5)";
  ctx.fillRect(0, 0, fieldW, 26);
  ctx.font = "bold 14px system-ui, sans-serif";
  ctx.textBaseline = "middle";
  ctx.textAlign = "left";
  ctx.fillStyle = "#6fb3ff";
  ctx.fillText("AGENTS " + hud.blue_count, 12, 13);
  ctx.fillStyle = "#ff6b6b";
  ctx.fillText("BUGS " + hud.red_count, 150, 13);
  ctx.fillStyle = "#e8eef7";
  ctx.textAlign = "center";
  ctx.fillText(hud.level_name || "LV " + hud.level, fieldW / 2, 13);
  ctx.fillStyle = "#ffd479";
  ctx.textAlign = "right";
  ctx.fillText("TOKENS " + hud.tokens, fieldW - 12, 13);

  if (hud.upgrades) {
    var u = hud.upgrades;
    ctx.fillStyle = "#9fb0c9";
    ctx.font = "bold 10px system-ui, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(
      "FIRE " + (u.fire_rate || 0) +
        " · MULTI " + (u.multishot || 0) +
        " · SPEED " + (u.speed || 0),
      fieldW - 8,
      PLAYER_BASE_Y + 10
    );
  }
}

function render(now) {
  var s = latest || DEFAULT_STATE;
  var dx = 0;
  var dy = 0;
  if (motion && now < playerFlashUntil) {
    var t = (playerFlashUntil - now) / SHAKE_MS;
    dx = (Math.random() * 2 - 1) * 5 * t;
    dy = (Math.random() * 2 - 1) * 3 * t;
  }
  ctx.save();
  ctx.translate(dx, dy);
  drawField();
  drawFortress(s, now);
  drawBase(s, now);
  drawGates(s);
  drawUnits(s.blue, "#4a90ff");
  drawBugs(s.red);
  drawLauncher(s);
  if (motion) drawParticles();
  ctx.restore();
  drawDamageGlow(now);
  drawHud(s);
}

// ---------------------------------------------------------------------------
// Overlay (connecting / paused / won / lost)
// ---------------------------------------------------------------------------
var overlayKey = null;

function shopRowHtml(up, hud) {
  var level = (hud.upgrades && hud.upgrades[up.key]) || 0;
  var price = (hud.prices || {})[up.key];
  if (price === undefined) price = null;
  var maxed = price === null;
  var afford = !maxed && hud.tokens >= price;
  var cls = "shop-row" + (maxed ? " max" : afford ? " afford" : " dim");
  return (
    '<div class="' + cls + '">' +
    '<span class="shop-key">' + up.num + "</span>" +
    '<span class="shop-name">' + up.label + "</span>" +
    '<span class="shop-lvl">Lv ' + level + " / " + up.max + "</span>" +
    '<span class="shop-price">' + (maxed ? "MAX" : price) + "</span>" +
    "</div>"
  );
}

function shopHtml(hud) {
  var rows = "";
  for (var i = 0; i < UPGRADES.length; i++) rows += shopRowHtml(UPGRADES[i], hud);
  return (
    '<div class="end">' +
    '<div class="end-title">SHIPPED!</div>' +
    '<div class="end-line">' + (hud.level_name || "Level cleared") + "</div>" +
    '<div class="end-tokens">TOKENS ' + (hud.tokens || 0) + "</div>" +
    '<div class="shop">' + rows + "</div>" +
    '<div class="end-hint">1 / 2 / 3 buy · N next level · R replay</div>' +
    "</div>"
  );
}

function campaignHtml(hud) {
  var u = hud.upgrades || {};
  return (
    '<div class="end">' +
    '<div class="end-title">CAMPAIGN COMPLETE</div>' +
    '<div class="end-line">Every production line is bug-free</div>' +
    '<div class="end-tokens">TOKENS ' + (hud.tokens || 0) + "</div>" +
    '<div class="end-line">Fire rate Lv ' + (u.fire_rate || 0) +
      " · Multishot Lv " + (u.multishot || 0) +
      " · Speed Lv " + (u.speed || 0) + "</div>" +
    '<div class="end-hint">Press R to replay</div>' +
    "</div>"
  );
}

function updateOverlay() {
  if (!overlay) return;
  var key;
  if (!haveState) {
    key = "connecting";
  } else if (!latest) {
    key = "playing";
  } else {
    var h = latest.hud || {};
    if (latest.status === "won" && h.upgrades) {
      var u = h.upgrades;
      // Include tokens/upgrades so a buy refreshes the shop while it is open.
      key = "won|" + (h.has_next ? 1 : 0) + "|" + (h.tokens || 0) + "|" +
        (u.fire_rate || 0) + "," + (u.multishot || 0) + "," + (u.speed || 0) + "|" +
        (h.level_name || "");
    } else {
      key = latest.status;
    }
  }
  // A resume we just sent still shows as paused in the next snapshot or two;
  // hide that so starting the game never flashes the PAUSED screen.
  if (latest && latest.status === "playing") resumePending = false;
  else if (resumePending && key === "paused") key = "playing";
  if (key === overlayKey) return;
  overlayKey = key;

  overlay.classList.remove("won", "lose");
  if (key === "connecting") {
    overlay.textContent = "Connecting…";
    overlay.classList.add("show");
  } else if (key === "paused") {
    overlay.textContent = "PAUSED\nPress P to resume";
    overlay.classList.add("show");
  } else if (latest && latest.status === "won") {
    var hud = latest.hud || {};
    if (hud.upgrades) {
      overlay.innerHTML = hud.has_next ? shopHtml(hud) : campaignHtml(hud);
    } else {
      var gained = Math.max(0, (hud.tokens || 0) - levelStartTokens);
      overlay.innerHTML =
        '<div class="end">' +
        '<div class="end-title">SHIPPED!</div>' +
        '<div class="end-line">Production is bug-free</div>' +
        '<div class="end-tokens">+' + gained + " tokens</div>" +
        '<div class="end-hint">Press R to play again</div>' +
        "</div>";
    }
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
// Title screen and help overlay
// ---------------------------------------------------------------------------
var menuKey = null;

function keysHtml() {
  return (
    '<div class="keys">' +
    "<div><kbd>←</kbd><kbd>→</kbd> / <kbd>A</kbd><kbd>D</kbd> move</div>" +
    "<div><kbd>Space</kbd> fire</div>" +
    "<div><kbd>P</kbd> pause · <kbd>R</kbd> restart</div>" +
    "<div><kbd>M</kbd> motion toggle · <kbd>H</kbd>/<kbd>?</kbd> help</div>" +
    "</div>"
  );
}

function titleHtml() {
  return (
    '<div class="menu-title">SWARM CONTROL</div>' +
    '<div class="menu-pitch">Push the bugs back and multiply through the gates.</div>' +
    keysHtml() +
    '<div class="menu-hint">Press Space to start</div>'
  );
}

function helpHtml() {
  return (
    '<div class="menu-title help">HOW TO PLAY</div>' +
    '<div class="menu-pitch">Push back the bugs, multiply through gates, win 3 levels.</div>' +
    keysHtml() +
    '<div class="keys">' +
    "<div><kbd>1</kbd><kbd>2</kbd><kbd>3</kbd> buy upgrades · <kbd>N</kbd> next · <kbd>R</kbd> restart</div>" +
    "</div>" +
    '<div class="menu-hint">H / ? / Esc to close</div>'
  );
}

function updateMenu() {
  if (!menu) return;
  var key = helpOpen ? "help" : !started ? "title" : "none";
  if (key === menuKey) return;
  menuKey = key;
  if (key === "none") {
    menu.classList.remove("show");
    return;
  }
  menu.innerHTML = key === "title" ? titleHtml() : helpHtml();
  menu.classList.add("show");
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
    if (mockMode && started && !helpOpen) {
      mockStep(dt);
      if (now - lastEmit >= 1000 / SEND_HZ) {
        latest = mockSnapshot();
        haveState = true;
        lastEmit = now;
      }
    }
    if (haveState && latest && started) {
      trackLevel(latest);
      trackDamage(latest, now);
      trackGates(latest, now);
    }
    if (motion) updateParticles(dt);
    render(now);
    updateOverlay();
    updateMenu();
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
