"""Headless performance benchmark for the Swarm Control simulation (phase 5).

Builds a level-1 world at several unit loads, steps it for >= 2 s of game
time, and reports per-step mean/p50/p95/max plus a phase breakdown obtained
by timing the World's own calls from the outside (no game-code edits).
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from swarm_control import config
from swarm_control.sim import world as world_module
from swarm_control.sim.waves import get_level
from swarm_control.sim.world import World

BUDGET_MS = 1000.0 / config.TICK_HZ
DT = 1.0 / config.TICK_HZ
DEFAULT_LOADS = (500, 1000, 2000, 3000, 4000)


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Swarm Control step-time benchmark")
    parser.add_argument(
        "--loads",
        default=",".join(str(n) for n in DEFAULT_LOADS),
        help="comma-separated total unit loads, e.g. '500,1000,4000'",
    )
    parser.add_argument("--seconds", type=float, default=2.0, help="game time per load (>= 2 s ideal)")
    parser.add_argument("--seed", type=int, default=0, help="rng seed for unit placement")
    parser.add_argument("--json", default=None, help="write results JSON to this file")
    parser.add_argument("--profile", action="store_true", help="cProfile the heaviest load")
    return parser.parse_args()


def parse_loads(text: str) -> list[int]:
    """Parse a comma-separated load list into positive ints."""
    loads = [int(part) for part in text.split(",") if part.strip()]
    if not loads or any(n <= 0 for n in loads):
        raise ValueError("--loads must be positive integers")
    return loads


def make_world(load: int, seed: int) -> World:
    """Build a level-1 world with `load` units spread like test_world_p3."""
    world = World(seed=seed, level=get_level(1))
    # Keep the game playing for the whole run so steps never become no-ops.
    world.enemy_hp = world.enemy_hp_max = 1.0e9
    world.player_hp = world.player_hp_max = 1.0e9
    half = load // 2
    rest = load - half
    rng = np.random.default_rng(seed + load)
    blue_x = rng.uniform(0, config.FIELD_W, half)
    blue_y = rng.uniform(400, 900, half)
    red_x = rng.uniform(0, config.FIELD_W, rest)
    red_y = rng.uniform(150, 500, rest)
    blue_slots = world.blue.spawn_many(blue_x, blue_y, vy=-config.AGENT_SPEED)
    world.red.spawn_many(red_x, red_y, vy=80.0)
    world.passed[blue_slots] = np.uint32(0)
    world.set_input(False, False, False)
    return world


def _time_wrapper(accum: dict[str, float], key: str, func: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap `func` so its wall time accumulates under `accum[key]`."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            accum[key] += time.perf_counter() - start

    return wrapper


def bench_load(load: int, seconds: float, seed: int) -> dict[str, Any]:
    """Step one load level and return timing statistics (seconds converted to ms)."""
    world = make_world(load, seed)
    steps = max(1, round(seconds * config.TICK_HZ))
    accum = {
        "launcher_fire": 0.0,
        "gate_move": 0.0,
        "movement": 0.0,
        "gates": 0.0,
        "waves": 0.0,
        "combat": 0.0,
        "bases": 0.0,
        "cleanup": 0.0,
    }
    # Wrap bound methods for per-phase timing (script-local monkeypatching).
    method_keys = {
        "_move_launcher": "launcher_fire",
        "_fire": "launcher_fire",
        "_move_units": "movement",
        "_apply_gates": "gates",
        "_spawn_waves": "waves",
        "_resolve_bases": "bases",
        "_cull": "cleanup",
    }
    originals: dict[str, Any] = {}
    for attr, key in method_keys.items():
        originals[attr] = getattr(world, attr)
        setattr(world, attr, _time_wrapper(accum, key, originals[attr]))
    orig_move_gates = world_module.move_gates
    orig_collide = world_module.collide
    world_module.move_gates = _time_wrapper(accum, "gate_move", orig_move_gates)  # type: ignore[method-assign]
    world_module.collide = _time_wrapper(accum, "combat", orig_collide)  # type: ignore[method-assign]
    try:
        step_times = np.empty(steps, dtype=np.float64)
        for i in range(steps):
            start = time.perf_counter()
            world.step(DT)
            step_times[i] = time.perf_counter() - start
    finally:
        for attr, func in originals.items():
            setattr(world, attr, func)
        world_module.move_gates = orig_move_gates  # type: ignore[method-assign]
        world_module.collide = orig_collide  # type: ignore[method-assign]

    total = float(step_times.sum())
    timed = sum(accum.values())
    phases = {
        "movement": accum["movement"] / steps,
        "gates": (accum["gate_move"] + accum["gates"]) / steps,
        "combat": accum["combat"] / steps,
        "bases_cleanup": (accum["bases"] + accum["cleanup"]) / steps,
        "other_launcher_waves": (accum["launcher_fire"] + accum["waves"]) / steps,
        # Tick bookkeeping / status checks between phases cannot be isolated
        # from World.step; report the residual instead of guessing.
        "step_overhead": (total - timed) / steps,
    }

    # Snapshot + pack cost on a fresh full-load world (30 Hz server path).
    snap_world = make_world(load, seed)
    n_snaps = max(10, round(1.0 * config.SEND_HZ))
    snap_times = np.empty(n_snaps, dtype=np.float64)
    for i in range(n_snaps):
        start = time.perf_counter()
        state = snap_world.snapshot()
        json.dumps(state)
        snap_times[i] = time.perf_counter() - start

    ms = step_times * 1000.0
    snap_ms = snap_times * 1000.0
    return {
        "load": load,
        "blue": half_count(load),
        "red": load - half_count(load),
        "steps": steps,
        "step_ms": {
            "mean": float(np.mean(ms)),
            "p50": float(np.percentile(ms, 50)),
            "p95": float(np.percentile(ms, 95)),
            "max": float(np.max(ms)),
        },
        "budget_ms": BUDGET_MS,
        "budget_frac": float(np.mean(ms) / BUDGET_MS),
        "phases_ms": {key: value * 1000.0 for key, value in phases.items()},
        "snapshot_ms": {
            "mean": float(np.mean(snap_ms)),
            "p95": float(np.percentile(snap_ms, 95)),
            "max": float(np.max(snap_ms)),
        },
    }


def half_count(load: int) -> int:
    """Return the blue share of a total load."""
    return load // 2


def print_table(rows: list[dict[str, Any]]) -> None:
    """Print an aligned text table of benchmark results."""
    header = (
        f"{'load':>6} {'mean':>8} {'p50':>8} {'p95':>8} {'max':>8} {'%budg':>7} "
        f"{'move':>8} {'gates':>8} {'combat':>8} {'base/cl':>8} {'snap':>8}"
    )
    print("Per-step time (ms) over >= 2 s of game time; budget = 60 Hz (16.7 ms).")
    print(header)
    print("-" * len(header))
    for row in rows:
        step = row["step_ms"]
        phases = row["phases_ms"]
        print(
            f"{row['load']:>6} {step['mean']:>8.3f} {step['p50']:>8.3f} "
            f"{step['p95']:>8.3f} {step['max']:>8.3f} {row['budget_frac'] * 100:>6.1f}% "
            f"{phases['movement']:>8.3f} {phases['gates']:>8.3f} "
            f"{phases['combat']:>8.3f} {phases['bases_cleanup']:>8.3f} "
            f"{row['snapshot_ms']['mean']:>8.3f}"
        )
    print()
    print("Phases: move=_move_units, gates=move_gates+_apply_gates, combat=collide,")
    print("  base/cl=_resolve_bases+_cull, snap=snapshot()+json.dumps (30 Hz path).")
    print("Launcher/fire/waves are timed but grouped outside the requested phases;")
    print("'step_overhead' (tick/status bookkeeping) cannot be isolated from")
    print("World.step from the outside, so the residual (total minus timed phases)")
    print("is reported in JSON instead of being guessed in the table.")


def run_profile(load: int, seconds: float, seed: int) -> None:
    """cProfile the heaviest load and print the top 15 functions by cumulative time."""
    world = make_world(load, seed)
    steps = max(1, round(seconds * config.TICK_HZ))
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(steps):
        world.step(DT)
    state = world.snapshot()
    json.dumps(state)
    profiler.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
    stats.print_stats(15)
    print(f"--- cProfile at load {load} ({steps} steps + 1 snapshot) ---")
    print(stream.getvalue())


def main() -> None:
    """Run the benchmark and print the table."""
    args = parse_args()
    loads = parse_loads(args.loads)
    seconds = float(args.seconds)
    rows = [bench_load(load, seconds, args.seed) for load in loads]
    print_table(rows)
    if args.profile:
        run_profile(max(loads), seconds, args.seed)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=2)
        print(f"Wrote JSON to {args.json}")


if __name__ == "__main__":
    main()
