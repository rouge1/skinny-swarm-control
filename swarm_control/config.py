"""Game constants shared by the simulation, server and client.

Coordinates are field pixels: origin top-left, x to the right, y downward.
The player's launcher sits near the bottom; the bug fortress ("Production")
sits at the top. Agents (blue) move up (negative vy); bugs (red) move down.
"""

FIELD_W = 540.0
FIELD_H = 960.0

TICK_HZ = 60  # simulation steps per second
SEND_HZ = 30  # state messages per second to the client

BLUE_CAPACITY = 4000
RED_CAPACITY = 4000

UNIT_RADIUS = 5.0

LAUNCHER_Y = 900.0
LAUNCHER_SPEED = 420.0  # px/s while an arrow key is held
LAUNCHER_MARGIN = 30.0  # launcher x is clamped to [MARGIN, FIELD_W - MARGIN]
FIRE_INTERVAL = 0.12  # seconds between shots while fire is held

AGENT_SPEED = 260.0  # px/s, upward

ENEMY_BASE_Y = 70.0  # centre line of the bug fortress
PLAYER_BASE_Y = 940.0  # bugs that reach this line damage the player

MUZZLE_OFFSET = 20.0  # agents spawn this far above the launcher

# --- phase 3: combat, gates, waves
ENEMY_HIT_Y = 110.0  # agents at or above this line hit the fortress (1 damage each)
BUG_SPAWN_Y = 120.0  # bugs enter just below the fortress
GATE_SCATTER = 12.0  # copies from a gate appear within this many px of their parent
MAX_GATES = 32  # a uint32 bit mask tracks which gates each agent has passed
