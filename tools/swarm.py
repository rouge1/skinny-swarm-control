#!/usr/bin/env python3
"""Swarm ops: run OpenCode workers, track time/tokens/cost, keep the event log.

The event log (data/events.jsonl) is the single source of truth. The live
dashboard and its replay are both folds over it; `push` exports it as one
timeline document per phase for the dashboard's database.
"""

import argparse
import fcntl
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "out"
EVENTS = DATA / "events.jsonl"
LEDGER = DATA / "ledger.jsonl"
LOGS = DATA / "logs"

MODELS = {
    "luna": {"id": "openrouter/openai/gpt-5.6-luna", "name": "GPT-5.6 Luna"},
    "muse": {"id": "openrouter/meta/muse-spark-1.3-contributor", "name": "Muse Spark 1.3 Contributor"},
    "flash": {"id": "openrouter/deepseek/deepseek-v4.1-flash", "name": "DeepSeek V4.1 Flash"},
}

PHASES = [
    {"id": "p0", "title": "Foundations", "goal": "Repo, interfaces, acceptance tests, worker rules.",
     "exit": "Test suite runs; stubs import; contracts documented."},
    {"id": "p1", "title": "Bake-off", "goal": "All three models build the same UnitPool from the same spec.",
     "exit": "Winner merged; per-model scorecard recorded."},
    {"id": "p2", "title": "Walking skeleton", "goal": "World core, WebSocket server, canvas client in parallel.",
     "exit": "Open the page, press Space, agents fly up the field."},
    {"id": "p3", "title": "Core gameplay", "goal": "Multiplier gates, bug waves, collisions, bases, HUD.",
     "exit": "A level can be won and lost."},
    {"id": "p4", "title": "Meta layer", "goal": "Levels, agent types, launch modes, token economy, menus.",
     "exit": "Play three levels in a row with upgrades between them."},
    {"id": "p5", "title": "Polish", "goal": "Performance, balance, playtest, final review.",
     "exit": "2,000+ units at 60 fps; full playthrough in Chrome."},
]


def now_ms() -> int:
    return int(time.time() * 1000)


def emit(ev: dict) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    ev = {"t": now_ms(), **ev}
    with open(EVENTS, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(ev) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)
    return ev


def load_events() -> list[dict]:
    if not EVENTS.exists():
        return []
    return [json.loads(line) for line in EVENTS.read_text().splitlines() if line.strip()]


def current_phase(events: list[dict]) -> str:
    cur = "p0"
    for e in events:
        if e["type"] == "phase" and e["status"] == "active":
            cur = e["phase"]
    return cur


# ---------------------------------------------------------------- run


def session_metrics(session_id: str, since_ms: int) -> dict:
    """Cost, tokens and model time for assistant messages created since `since_ms`."""
    # stdout to a pipe is truncated at ~64 KB by opencode; a file is not
    tmp = LOGS / f"export-{session_id}.json"
    with open(tmp, "w") as f:
        subprocess.run(["opencode", "export", session_id], stdout=f, stderr=subprocess.DEVNULL, cwd="/tmp")
    raw = tmp.read_text()
    tmp.unlink()
    start = raw.find("{")
    data = json.loads(raw[start:]) if start >= 0 else {"messages": []}
    m = {"cost": 0.0, "tokens_in": 0, "tokens_out": 0, "tokens_reasoning": 0, "cache_read": 0,
         "model_s": 0.0, "messages": 0, "files_changed": 0}
    for msg in data.get("messages", []):
        info = msg.get("info", {})
        if info.get("role") != "assistant" or info.get("time", {}).get("created", 0) < since_ms:
            continue
        t = info.get("tokens", {})
        m["cost"] += info.get("cost", 0.0) or 0.0
        m["tokens_in"] += t.get("input", 0)
        m["tokens_out"] += t.get("output", 0)
        m["tokens_reasoning"] += t.get("reasoning", 0)
        m["cache_read"] += t.get("cache", {}).get("read", 0)
        tm = info.get("time", {})
        if tm.get("completed"):
            m["model_s"] += (tm["completed"] - tm["created"]) / 1000
        m["messages"] += 1
    m["files_changed"] = data.get("info", {}).get("summary", {}).get("files", 0)
    m["cost"] = round(m["cost"], 6)
    m["model_s"] = round(m["model_s"], 1)
    return m


def cmd_run(a):
    model = MODELS[a.model]
    prompt = Path(a.prompt_file).read_text() if a.prompt_file else a.prompt
    kind = a.kind or ("fix" if a.session else "build")
    emit({"type": "task", "phase": a.phase, "task": a.task, "model": a.model,
          "status": "fixing" if kind == "fix" else "working"})
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{a.phase}-{a.task}-{a.model}-{now_ms()}.jsonl"
    cmd = ["opencode", "run", "--format", "json", "-m", model["id"], "--dir", a.dir,
           "--title", f"{a.phase}/{a.task}/{a.model}"]
    if a.session:
        cmd += ["-s", a.session]
    cmd.append(prompt)
    start = now_ms()
    t0 = time.monotonic()
    timed_out = False
    with open(log, "w") as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=a.dir)
        # watchdog: kill on the overall timeout, or if the worker prints nothing for a.stall seconds
        while proc.poll() is None:
            time.sleep(2)
            st = log.stat()
            idle = time.time() - st.st_mtime
            # a run that never prints is hung; one that has started may be quietly writing a big file
            limit = a.stall if st.st_size == 0 else a.stall_active
            if time.monotonic() - t0 > a.timeout or idle > limit:
                proc.kill()
                proc.wait()
                timed_out = True
                break
        code = -1 if timed_out else proc.returncode
    wall = round(time.monotonic() - t0, 1)
    finalize(a, kind, start, wall, code, timed_out, log)


def finalize(a, kind, start, wall, code, timed_out, log):
    sid = a.session
    if not sid:
        found = re.findall(r'"sessionID"\s*:\s*"(ses_[A-Za-z0-9]+)"', log.read_text())
        sid = found[0] if found else None
    metrics = session_metrics(sid, start) if sid else {}
    if getattr(a, "text_out", None):
        # keep the worker's final written answer (used for OpenCode reviews)
        texts = []
        for line in log.read_text().splitlines():
            try:
                part = json.loads(line).get("part", {})
            except ValueError:
                continue
            if part.get("type") == "text" and part.get("text"):
                texts.append(part["text"])
        Path(a.text_out).write_text(texts[-1] if texts else "")
    rec = {"phase": a.phase, "task": a.task, "model": a.model, "kind": kind, "session": sid,
           "wall_s": wall, "exit": code, "timed_out": timed_out, "log": str(log), **metrics}
    with open(LEDGER, "a") as f:
        f.write(json.dumps({"t": now_ms(), **rec}) + "\n")
    emit({"type": "run", **{k: v for k, v in rec.items() if k != "log"}})
    emit({"type": "task", "phase": a.phase, "task": a.task, "model": a.model,
          "status": "review" if code == 0 else "failed",
          **({"note": "timed out"} if timed_out else {})})
    print(json.dumps(rec, indent=1))


# ---------------------------------------------------------------- simple events


def cmd_recover(a):
    """Rebuild the ledger entry for a finished run whose bookkeeping failed, from its log."""
    log = Path(a.log)
    start = int(re.search(r"-(\d{13})\.jsonl$", log.name).group(1))
    wall = round(log.stat().st_mtime - start / 1000, 1)
    a.session = None
    finalize(a, a.kind, start, wall, 0, False, log)


def cmd_phase(a):
    emit({"type": "phase", "phase": a.phase, "status": a.status})


def cmd_task(a):
    if not a.model:
        # fill in the worker from earlier events so a status change never creates an ownerless card
        owners = {e.get("model") for e in load_events()
                  if e["type"] == "task" and e["phase"] == a.phase and e["task"] == a.task and e.get("model")}
        if len(owners) > 1:
            sys.exit(f"task {a.phase}/{a.task} has several workers {sorted(owners)}; pass --model")
        a.model = owners.pop() if owners else None
    ev = {"type": "task", "phase": a.phase, "task": a.task, "status": a.status}
    for k in ("model", "title", "note", "files"):
        if getattr(a, k):
            ev[k] = getattr(a, k)
    emit(ev)


def cmd_note(a):
    emit({"type": "note", "phase": a.phase or current_phase(load_events()), "who": a.who, "text": a.text})


def cmd_review(a):
    emit({"type": "review", "phase": a.phase, "task": a.task, "model": a.model, "verdict": a.verdict,
          "findings": a.findings, "wall_s": a.wall, "summary": a.summary or ""})


def cmd_tests(a):
    emit({"type": "tests", "phase": a.phase, "task": a.task, "model": a.model,
          "passed": a.passed, "failed": a.failed})


def cmd_crew(a):
    emit({"type": "crew", "phase": a.phase or current_phase(load_events()), "who": a.who,
          "state": a.state, "doing": a.doing or ""})


def cmd_score(a):
    emit({"type": "score", "phase": a.phase, "task": a.task, "model": a.model, "score": a.score,
          "summary": a.summary or ""})


# ---------------------------------------------------------------- status


def fmt_s(s: float) -> str:
    s = int(round(s))
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


def cmd_status(a):
    events = load_events()
    cur = current_phase(events)
    tasks = {}
    for e in events:
        if e["type"] == "task":
            key = (e["phase"], e["task"], e.get("model"))
            tasks.setdefault(key, {}).update(e)
    title = next(p["title"] for p in PHASES if p["id"] == cur)
    print(f"Current phase: {cur} · {title}\n")
    for (ph, task, model), t in tasks.items():
        if ph == cur:
            name = MODELS.get(model, {}).get("name", model or "orchestrator")
            print(f"  {task:<18} {name:<28} {t['status']}")
    agg = defaultdict(lambda: defaultdict(float))
    for e in events:
        if e["type"] == "run":
            r = agg[(e["phase"], e["model"])]
            r["runs"] += 1
            r["fix"] += e["kind"] == "fix"
            r["wall"] += e["wall_s"]
            r["model_s"] += e.get("model_s", 0)
            r["tokens"] += e.get("tokens_in", 0) + e.get("tokens_out", 0)
            r["cost"] += e.get("cost", 0)
    if agg:
        print(f"\n{'phase':<6}{'model':<28}{'runs':>5}{'fixes':>6}{'wall':>10}{'model':>10}{'tokens':>10}{'cost':>9}")
        tot = defaultdict(float)
        for (ph, m), r in sorted(agg.items()):
            print(f"{ph:<6}{MODELS[m]['name']:<28}{int(r['runs']):>5}{int(r['fix']):>6}{fmt_s(r['wall']):>10}"
                  f"{fmt_s(r['model_s']):>10}{int(r['tokens']):>10,}{r['cost']:>9.4f}")
            for k, v in r.items():
                tot[k] += v
        print(f"{'':<6}{'TOTAL':<28}{int(tot['runs']):>5}{int(tot['fix']):>6}{fmt_s(tot['wall']):>10}"
              f"{fmt_s(tot['model_s']):>10}{int(tot['tokens']):>10,}{tot['cost']:>9.4f}")


# ---------------------------------------------------------------- push


def cmd_push(a):
    """Write dashboard documents to out/; print the ones that changed since the last push."""
    OUT.mkdir(parents=True, exist_ok=True)
    events = load_events()
    docs = {("project", "meta"): {
        "name": "Swarm Control", "repo": "learn/swarm-control", "phases": PHASES,
        "models": [{"key": k, **v} for k, v in MODELS.items()],
    }}
    by_phase = defaultdict(list)
    for e in events:
        by_phase[e.get("phase") or "p0"].append(e)
    for ph, evs in by_phase.items():
        docs[("timeline", ph)] = {"phase": ph, "events": evs}
    cache_f = OUT / ".hashes.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    ver_f = OUT / ".versions.json"
    vers = json.loads(ver_f.read_text()) if ver_f.exists() else {}
    for kv in a.resync or []:
        k, v = kv.split("=")
        vers[k] = int(v)
    changed = []
    for (coll, doc_id), body in docs.items():
        path = OUT / f"{coll}__{doc_id}.json"
        text = json.dumps(body, separators=(",", ":"))
        h = hashlib.sha1(text.encode()).hexdigest()
        path.write_text(text)
        if a.all or cache.get(path.name) != h:
            w = {"op": "set", "collection": coll, "doc_id": doc_id, "file_path": str(path)}
            key = f"{coll}/{doc_id}"
            if key in vers:
                w["if_version"] = vers[key]
            vers[key] = vers.get(key, 0) + 1  # assumes the write lands; --resync fixes drift
            changed.append(w)
        cache[path.name] = h
    cache_f.write_text(json.dumps(cache))
    ver_f.write_text(json.dumps(vers))
    print(json.dumps(changed))


def cmd_export(a):
    """Bundle the event log into a standalone replay page (no database needed)."""
    page = (ROOT / "dashboard.html").read_text()
    payload = {"meta": {"name": "Swarm Control", "phases": PHASES,
                        "models": [{"key": k, **v} for k, v in MODELS.items()]},
               "events": load_events()}
    inject = f"<script>window.__SWARM_EMBED__ = {json.dumps(payload)};</script>\n"
    out = Path(a.out)
    out.write_text(inject + page)
    print(out)


# ---------------------------------------------------------------- claude usage

# $ per million tokens (Anthropic list prices): input, output, cache read, cache write 5m, cache write 1h
CLAUDE_PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00, 8.00),
    "claude-sonnet-5": (2.00, 10.00, 0.20, 2.50, 4.00),
    "claude-haiku-4-5": (1.00, 5.00, 0.10, 1.25, 2.00),
}
CLAUDE_NAMES = {"claude-opus-5-5": "Opus 5.5", "claude-sonnet-5": "Sonnet 5", "claude-haiku-4-5": "Haiku 4.5"}
SESSION_DIR = Path.home() / ".claude/projects/-data-python-learn"


def _price_key(model: str) -> str:
    for k in CLAUDE_PRICES:
        if model and model.startswith(k):
            return k
    return model or "unknown"


def _read_transcript(path: Path) -> list[dict]:
    """One entry per API message (streamed blocks repeat the same message id; keep the last)."""
    msgs = {}
    for line in path.open():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        m = e.get("message") or {}
        if e.get("type") == "assistant" and m.get("usage") and m.get("id"):
            msgs[m["id"]] = {"t": e.get("timestamp"), "model": m.get("model"), "u": m["usage"]}
    return list(msgs.values())


def cmd_claude(a):
    """Tally Claude (orchestrator + subagent) tokens and list-price cost per phase and model; log changes."""
    from datetime import datetime

    session = SESSION_DIR / f"{a.session}.jsonl"
    sources = [("orchestrator", session)]
    sources += [("reviewer", f) for f in sorted((SESSION_DIR / a.session / "subagents").glob("agent-*.jsonl"))]
    events = load_events()
    starts = [(e["t"], e["phase"]) for e in events if e["type"] == "phase" and e["status"] == "active"]

    def phase_at(ms):
        ph = "p0"
        for t, p in starts:
            if t <= ms:
                ph = p
        return ph

    agg = defaultdict(lambda: defaultdict(float))
    for role, path in sources:
        for m in _read_transcript(path):
            ms = int(datetime.fromisoformat(m["t"].replace("Z", "+00:00")).timestamp() * 1000)
            key = _price_key(m["model"])
            u = m["u"]
            cc = u.get("cache_creation") or {}
            w1h = cc.get("ephemeral_1h_input_tokens", 0) or 0
            w5m = (u.get("cache_creation_input_tokens", 0) or 0) - w1h
            r = agg[(phase_at(ms), role, key)]
            r["messages"] += 1
            r["input"] += u.get("input_tokens", 0) or 0
            r["output"] += u.get("output_tokens", 0) or 0
            r["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
            r["cache_write"] += w5m + w1h
            pi, po, pr, pw5, pw1 = CLAUDE_PRICES.get(key, (0, 0, 0, 0, 0))
            r["cost"] += (r_in := (u.get("input_tokens", 0) or 0)) * pi / 1e6 + (u.get("output_tokens", 0) or 0) * po / 1e6
            r["cost"] += (u.get("cache_read_input_tokens", 0) or 0) * pr / 1e6 + w5m * pw5 / 1e6 + w1h * pw1 / 1e6
            del r_in
    # log only what changed since the last tally
    last = {}
    for e in events:
        if e["type"] == "claude":
            last[(e["phase"], e["role"], e["model"])] = e
    changed = 0
    for (ph, role, model), r in sorted(agg.items()):
        ev = {"type": "claude", "phase": ph, "role": role, "model": model, "name": CLAUDE_NAMES.get(model, model),
              "messages": int(r["messages"]), "input": int(r["input"]), "output": int(r["output"]),
              "cache_read": int(r["cache_read"]), "cache_write": int(r["cache_write"]), "cost": round(r["cost"], 4)}
        prev = last.get((ph, role, model))
        if not prev or prev["messages"] != ev["messages"] or prev["output"] != ev["output"]:
            emit(ev)
            changed += 1
    tot = defaultdict(lambda: defaultdict(float))
    for (ph, role, model), r in agg.items():
        for k, v in r.items():
            tot[(role, model)][k] += v
    print(f"{'role':<13}{'model':<11}{'msgs':>6}{'output':>10}{'cache rd':>12}{'cache wr':>11}{'cost':>10}")
    for (role, model), r in sorted(tot.items()):
        print(f"{role:<13}{CLAUDE_NAMES.get(model, model):<11}{int(r['messages']):>6}{int(r['output']):>10,}"
              f"{int(r['cache_read']):>12,}{int(r['cache_write']):>11,}{r['cost']:>10.2f}")
    print(f"logged {changed} changed tallies")


def main():
    p = argparse.ArgumentParser(prog="swarm")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run")
    r.add_argument("phase"); r.add_argument("task"); r.add_argument("model", choices=MODELS)
    r.add_argument("--dir", required=True)
    r.add_argument("--prompt"); r.add_argument("--prompt-file")
    r.add_argument("--session"); r.add_argument("--timeout", type=int, default=1800)
    r.add_argument("--stall", type=int, default=120, help="kill if the run prints nothing at all for this long")
    r.add_argument("--stall-active", type=int, default=600, help="kill if a started run goes quiet this long")
    r.add_argument("--text-out", help="save the worker's final text answer to this file")
    r.add_argument("--kind", help="override run kind (e.g. review)")
    r.set_defaults(fn=cmd_run)

    s = sub.add_parser("recover"); s.add_argument("phase"); s.add_argument("task")
    s.add_argument("model", choices=MODELS); s.add_argument("log"); s.add_argument("--kind", default="build")
    s.set_defaults(fn=cmd_recover)

    s = sub.add_parser("phase"); s.add_argument("phase"); s.add_argument("status", choices=["active", "done"])
    s.set_defaults(fn=cmd_phase)

    s = sub.add_parser("task"); s.add_argument("phase"); s.add_argument("task")
    s.add_argument("status", choices=["queued", "working", "review", "fixing", "merged", "failed", "dropped"])
    s.add_argument("--model"); s.add_argument("--title"); s.add_argument("--note"); s.add_argument("--files")
    s.set_defaults(fn=cmd_task)

    s = sub.add_parser("note"); s.add_argument("text"); s.add_argument("--phase")
    s.add_argument("--who", default="orchestrator"); s.set_defaults(fn=cmd_note)

    s = sub.add_parser("review"); s.add_argument("phase"); s.add_argument("task"); s.add_argument("model")
    s.add_argument("verdict", choices=["pass", "changes"]); s.add_argument("--findings", type=int, default=0)
    s.add_argument("--wall", type=float, default=0); s.add_argument("--summary"); s.set_defaults(fn=cmd_review)

    s = sub.add_parser("tests"); s.add_argument("phase"); s.add_argument("task"); s.add_argument("model")
    s.add_argument("--passed", type=int, required=True); s.add_argument("--failed", type=int, required=True)
    s.set_defaults(fn=cmd_tests)

    s = sub.add_parser("score"); s.add_argument("phase"); s.add_argument("task"); s.add_argument("model")
    s.add_argument("score", type=float); s.add_argument("--summary"); s.set_defaults(fn=cmd_score)

    s = sub.add_parser("crew"); s.add_argument("who", choices=["orchestrator", "reviewer"])
    s.add_argument("state", choices=["busy", "idle"]); s.add_argument("doing", nargs="?")
    s.add_argument("--phase"); s.set_defaults(fn=cmd_crew)

    s = sub.add_parser("claude"); s.add_argument("--session", default="b6c19da9-a3c7-4204-84fa-c4434b1029c2")
    s.set_defaults(fn=cmd_claude)

    sub.add_parser("status").set_defaults(fn=cmd_status)
    s = sub.add_parser("push"); s.add_argument("--all", action="store_true")
    s.add_argument("--resync", nargs="*", help="coll/doc=version pairs from the database")
    s.set_defaults(fn=cmd_push)
    s = sub.add_parser("export"); s.add_argument("--out", default=str(OUT / "swarm-replay.html"))
    s.set_defaults(fn=cmd_export)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
