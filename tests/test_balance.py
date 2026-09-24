"""Phase 5 balance acceptance tests.

These tests intentionally run the headless simulation for many game seconds;
the runtime is part of the acceptance-test tradeoff and is kept bounded by the
same 180-second per-run budget as the balance report.
"""

import statistics
from dataclasses import dataclass

from swarm_control import config
from swarm_control.sim.waves import get_level
from swarm_control.sim.world import World

DT = 1.0 / config.TICK_HZ
MAX_SECONDS = 180.0
LEVELS = (1, 2, 3)
SWEEP_SEEDS = (1, 2, 3)
STATIONARY_SEEDS = (1, 2)
STAND_X = (90.0, 180.0, 270.0, 360.0, 450.0)


@dataclass(frozen=True)
class Run:
    """Outcome and elapsed game time for one scripted run."""

    outcome: str
    seconds: float


_RUNS: dict[tuple[str, int, int], Run] = {}


def _input(kind: str, second: int) -> tuple[bool, bool, bool]:
    """Return the input held during one second of a scripted player."""
    if kind == "idle":
        return False, False, False
    if kind == "stand":
        return False, False, True
    period = 2 if kind == "sweep" else 1
    phase = (second // period) % 2
    return phase == 0, phase == 1, True


def _play(kind: str, level_number: int, seed: int, launcher_x: float | None = None) -> Run:
    """Run one scripted player against one level and seed."""
    cache_key = (kind, level_number, seed)
    if launcher_x is None and cache_key in _RUNS:
        return _RUNS[cache_key]

    world = World(seed=seed, level=get_level(level_number))
    if launcher_x is not None:
        world.launcher_x = launcher_x
    max_steps = round(MAX_SECONDS * config.TICK_HZ)
    for step in range(max_steps):
        world.set_input(*_input(kind, step // config.TICK_HZ))
        world.step(DT)
        if world.status != "playing":
            break

    result = Run(
        outcome="timeout" if world.status == "playing" else world.status,
        seconds=min(world.elapsed, MAX_SECONDS),
    )
    if launcher_x is None:
        _RUNS[cache_key] = result
    return result


def _campaign_run(level_number: int, seed: int) -> Run:
    """Play through level three, greedily buying upgrades between levels."""
    world = World(seed=seed, level=get_level(1))
    results: dict[int, Run] = {}
    upgrade_actions = {
        "fire_rate": "buy_fire_rate",
        "multishot": "buy_multishot",
        "speed": "buy_speed",
    }
    for current_level in LEVELS:
        if current_level > 1:
            world.action("next")
        max_steps = round(MAX_SECONDS * config.TICK_HZ)
        for step in range(max_steps):
            world.set_input(*_input("sweep", step // config.TICK_HZ))
            world.step(DT)
            if world.status != "playing":
                break
        results[current_level] = Run(
            outcome="timeout" if world.status == "playing" else world.status,
            seconds=min(world.elapsed, MAX_SECONDS),
        )
        if current_level == level_number:
            return results[current_level]

        while world.status == "won":
            prices = world.snapshot()["hud"]["prices"]
            affordable = [
                (int(price), key)
                for key, price in prices.items()
                if price is not None and int(price) <= world.tokens
            ]
            if not affordable:
                break
            _price, key = min(affordable)
            world.action(upgrade_actions[key])
    raise AssertionError(f"campaign did not reach level {level_number}")


def test_idle_and_standing_players_lose_every_level() -> None:
    """Idle and fixed-position firing must never defeat any level."""
    players = [("idle", None), *[("stand", x) for x in STAND_X]]
    for kind, launcher_x in players:
        for level_number in LEVELS:
            for seed in STATIONARY_SEEDS:
                result = _play(kind, level_number, seed, launcher_x)
                assert result.outcome == "lost", (
                    f"{kind}@{launcher_x} level {level_number} seed {seed}: "
                    f"expected loss, got {result.outcome}"
                )


def test_sweep_wins_all_levels_and_has_target_times() -> None:
    """The two-second sweep must win reliably with level-specific pacing."""
    bounds = {1: (45.0, 75.0), 2: (70.0, 100.0), 3: (95.0, 130.0)}
    for level_number in LEVELS:
        runs = [_play("sweep", level_number, seed) for seed in SWEEP_SEEDS]
        assert all(run.outcome == "won" for run in runs), (
            f"sweep level {level_number} outcomes: {[run.outcome for run in runs]}"
        )
        median_time = statistics.median(run.seconds for run in runs)
        low, high = bounds[level_number]
        assert low <= median_time <= high, (
            f"sweep level {level_number} median {median_time:.2f}s outside {low}-{high}s"
        )
    medians = [
        statistics.median(_play("sweep", level_number, seed).seconds for seed in SWEEP_SEEDS)
        for level_number in LEVELS
    ]
    assert medians[0] < medians[1] < medians[2], f"sweep medians are not increasing: {medians}"


def test_sweep_fast_wins_every_level_and_seed() -> None:
    """A one-second sweep must also win every level for every sampled seed."""
    for level_number in LEVELS:
        for seed in SWEEP_SEEDS:
            result = _play("sweep_fast", level_number, seed)
            assert result.outcome == "won", (
                f"sweep-fast level {level_number} seed {seed}: got {result.outcome}"
            )


def test_campaign_upgrades_make_each_level_faster() -> None:
    """Greedy campaign upgrades must improve every post-reward level's time."""
    # Level 1 is necessarily played without upgrades so its reward can be
    # earned; levels 2 and 3 are the upgraded comparisons.
    for level_number in LEVELS[1:]:
        baseline = [_play("sweep", level_number, seed).seconds for seed in SWEEP_SEEDS]
        upgraded = [_campaign_run(level_number, seed) for seed in SWEEP_SEEDS]
        assert all(run.outcome == "won" for run in upgraded), (
            f"upgraded level {level_number} outcomes: {[run.outcome for run in upgraded]}"
        )
        baseline_median = statistics.median(baseline)
        upgraded_median = statistics.median(run.seconds for run in upgraded)
        assert upgraded_median < baseline_median, (
            f"level {level_number} upgrade median {upgraded_median:.2f}s is not "
            f"faster than baseline {baseline_median:.2f}s"
        )
