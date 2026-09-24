"""Headless balance report for Swarm Control levels (phase 5 tuning).

Runs a handful of deterministic scripted players against every level in
``swarm_control.sim.waves.LEVELS`` for several seeds and prints an aligned
summary table:

    python scripts/balance.py --seeds 2 [--json report.json]

Players (all at a fixed dt = 1 / TICK_HZ, for up to 180 s of game time):

    sweep       fire while sweeping left/right every 2 s (as in the P3 tests)
    sweep-fast  fire while sweeping left/right every 1 s
    idle        never fires
    stand@X     hold fire without moving, launcher pinned at x = X

Per level and player the report lists the win rate, median/min/max time to a
result, the median final HP of both bases, the peak unit counts, and a final
WARNINGS list for balance problems. ``--json`` writes the same data to a file.
"""

import argparse
import dataclasses
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarm_control import config  # noqa: E402
from swarm_control.sim.waves import LEVELS, get_level  # noqa: E402
from swarm_control.sim.world import World  # noqa: E402

DT = 1.0 / config.TICK_HZ
MAX_SECONDS = 180.0
STAND_X = (90.0, 180.0, 270.0, 360.0, 450.0)


@dataclasses.dataclass
class RunResult:
    """Outcome of one scripted run of one player on one level and seed."""

    seed: int
    status: str
    seconds: float
    enemy_hp: float
    player_hp: float
    peak_blue: int
    peak_red: int


@dataclasses.dataclass(frozen=True)
class Player:
    """A scripted player: name, behaviour kind and optional fixed launcher x."""

    name: str
    kind: str
    x: float | None = None


PLAYERS: list[Player] = [
    Player("sweep", "sweep"),
    Player("sweep-fast", "sweep_fast"),
    Player("idle", "idle"),
    *[Player(f"stand@{int(x)}", "stand", x) for x in STAND_X],
]


def _input_for(player: Player, second: int) -> tuple[bool, bool, bool]:
    """Return (left, right, fire) for one second of a scripted player."""
    if player.kind == "idle":
        return False, False, False
    if player.kind == "stand":
        return False, False, True
    period = 2 if player.kind == "sweep" else 1
    phase = (second // period) % 2
    return phase == 0, phase == 1, True


def play(player: Player, level_number: int, seed: int) -> RunResult:
    """Run one scripted player on one level/seed and return its outcome."""
    world = World(seed=seed, level=get_level(level_number))
    if player.x is not None:
        world.launcher_x = float(player.x)

    peak_blue = 0
    peak_red = 0
    steps = round(MAX_SECONDS * config.TICK_HZ)
    step = 0
    while step < steps and world.status == "playing":
        world.set_input(*_input_for(player, step // config.TICK_HZ))
        for _ in range(config.TICK_HZ):
            world.step(DT)
            peak_blue = max(peak_blue, world.blue.count)
            peak_red = max(peak_red, world.red.count)
            if world.status != "playing":
                break
        step += config.TICK_HZ

    seconds = min(world.elapsed, MAX_SECONDS)
    return RunResult(
        seed=seed,
        status=world.status,
        seconds=seconds,
        enemy_hp=world.enemy_hp,
        player_hp=world.player_hp,
        peak_blue=peak_blue,
        peak_red=peak_red,
    )


@dataclasses.dataclass
class Summary:
    """Aggregated runs for one (level, player) pair across all seeds."""

    level: int
    level_name: str
    player: str
    runs: list[RunResult]

    @property
    def wins(self) -> int:
        return sum(run.status == "won" for run in self.runs)

    @property
    def win_rate(self) -> float:
        return self.wins / len(self.runs)

    @property
    def times(self) -> list[float]:
        return [run.seconds for run in self.runs]

    def as_dict(self) -> dict:
        """Return a JSON-serialisable view of this summary."""
        times = self.times
        return {
            "level": self.level,
            "level_name": self.level_name,
            "player": self.player,
            "runs": len(self.runs),
            "wins": self.wins,
            "win_rate": self.win_rate,
            "time": {
                "median": statistics.median(times),
                "min": min(times),
                "max": max(times),
            },
            "enemy_hp_median": statistics.median([r.enemy_hp for r in self.runs]),
            "player_hp_median": statistics.median([r.player_hp for r in self.runs]),
            "peak_blue": max(r.peak_blue for r in self.runs),
            "peak_red": max(r.peak_red for r in self.runs),
            "per_seed": [dataclasses.asdict(r) for r in self.runs],
        }


def collect(seeds: list[int]) -> list[Summary]:
    """Run every player on every level for every seed, with stderr progress."""
    summaries: list[Summary] = []
    total = len(LEVELS) * len(PLAYERS) * len(seeds)
    done = 0
    for level in LEVELS:
        level_number = int(level["id"])
        for player in PLAYERS:
            runs = []
            for seed in seeds:
                done += 1
                print(
                    f"[{done}/{total}] level {level_number} {player.name} seed {seed}",
                    file=sys.stderr,
                    flush=True,
                )
                runs.append(play(player, level_number, seed))
            summaries.append(Summary(level_number, level["name"], player.name, runs))
    return summaries


def find_warnings(summaries: list[Summary]) -> list[str]:
    """Return human-readable balance warnings for the collected summaries."""
    warnings: list[str] = []
    for summary in summaries:
        if summary.player == "idle" or summary.player.startswith("stand"):
            if summary.wins:
                warnings.append(
                    f"level {summary.level}: a {summary.player} player won "
                    f"{summary.wins}/{len(summary.runs)} runs"
                )
        if summary.player in ("sweep", "sweep-fast") and summary.wins < len(summary.runs):
            warnings.append(
                f"level {summary.level}: {summary.player} lost "
                f"{len(summary.runs) - summary.wins}/{len(summary.runs)} runs"
            )

    sweep_players = ("sweep", "sweep-fast")
    by_player: dict[str, dict[int, float | None]] = {name: {} for name in sweep_players}
    for summary in summaries:
        if summary.player in sweep_players:
            win_times = [run.seconds for run in summary.runs if run.status == "won"]
            by_player[summary.player][summary.level] = (
                statistics.median(win_times) if win_times else None
            )
    for player_name, win_times_by_level in by_player.items():
        levels = sorted(win_times_by_level)
        for earlier, later in zip(levels, levels[1:], strict=False):
            first = win_times_by_level[earlier]
            second = win_times_by_level[later]
            if first is not None and second is not None and second < first:
                warnings.append(
                    f"difficulty falls: {player_name} wins level {later} in {second:.1f}s "
                    f"but level {earlier} takes {first:.1f}s"
                )
    return warnings


def print_table(summaries: list[Summary]) -> None:
    """Print the aligned report table to stdout."""
    header = (
        f"{'Level':>5}  {'Player':<11}  {'Win%':>5}  "
        f"{'T-med':>7}  {'T-min':>7}  {'T-max':>7}  "
        f"{'EnemyHP':>8}  {'PlayerHP':>8}  {'BluePk':>7}  {'RedPk':>6}"
    )
    print(header)
    print("-" * len(header))
    for summary in summaries:
        times = summary.times
        print(
            f"{summary.level:>5}  {summary.player:<11}  "
            f"{100.0 * summary.win_rate:>5.0f}  "
            f"{statistics.median(times):>7.1f}  {min(times):>7.1f}  {max(times):>7.1f}  "
            f"{statistics.median([r.enemy_hp for r in summary.runs]):>8.1f}  "
            f"{statistics.median([r.player_hp for r in summary.runs]):>8.1f}  "
            f"{max(r.peak_blue for r in summary.runs):>7}  "
            f"{max(r.peak_red for r in summary.runs):>6}"
        )


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the report and print it."""
    parser = argparse.ArgumentParser(description="Headless Swarm Control balance report.")
    parser.add_argument("--seeds", type=int, default=5, help="run seeds 1..N (default 5)")
    parser.add_argument("--json", metavar="PATH", help="also write the report as JSON to PATH")
    args = parser.parse_args(argv)

    if args.seeds < 1:
        parser.error("--seeds must be >= 1")
    seeds = list(range(1, args.seeds + 1))

    summaries = collect(seeds)
    warnings = find_warnings(summaries)

    print_table(summaries)
    print()
    print("WARNINGS")
    if warnings:
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("  (none)")

    if args.json:
        report = {
            "tick_hz": config.TICK_HZ,
            "dt": DT,
            "max_seconds": MAX_SECONDS,
            "seeds": seeds,
            "levels": [int(level["id"]) for level in LEVELS],
            "results": [summary.as_dict() for summary in summaries],
            "warnings": warnings,
        }
        Path(args.json).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
