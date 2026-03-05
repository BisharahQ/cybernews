#!/usr/bin/env python3
"""
SYSTEM ORCHESTRATOR — Jordan Cyber Intel Platform
==================================================
Single entry point that starts and manages all components.
Keeps every process alive, restarting on crash with backoff.

USAGE:
  python orchestrator.py          # Start everything
  python orchestrator.py --status # Print component status

COMPONENTS MANAGED:
  1. viewer.py          — Web UI + API (port 5000)
  2. telegram_monitor.py --live  — Live Telegram monitoring
  3. ai_agent.py        — AI enrichment + keyword learning + channel vetting

CONFIGURATION:
  Edit .env file in this directory:
    OPENAI_API_KEY=sk-...
    TG_API_ID=...
    TG_API_HASH=...
    TG_PHONE=+...

  Or set via admin panel at http://localhost:5000 (Settings tab)
"""

import os
import sys
import json
import time
import signal
import logging
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timezone

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
ENV_FILE   = BASE_DIR / ".env"
STATUS_FILE = BASE_DIR / "telegram_intel" / "orchestrator_status.json"
LOG_FILE   = BASE_DIR / "telegram_intel" / "orchestrator.log"

Path(BASE_DIR / "telegram_intel").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ORCH] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("Orchestrator")

# ── .env loader ────────────────────────────────────────────────────────────────
def load_env():
    """Load .env file into os.environ. Returns dict of loaded vars."""
    loaded = {}
    if not ENV_FILE.exists():
        return loaded
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and val:
            os.environ[key] = val
            loaded[key] = val
    return loaded

def save_env_key(key, value):
    """Write or update a single key in .env file."""
    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()

    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}=") or line.strip().startswith(f"{key} ="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.environ[key] = value
    log.info(f"Saved {key} to .env")


# ── Component definitions ──────────────────────────────────────────────────────
COMPONENTS = [
    {
        "name": "viewer",
        "cmd":  [sys.executable, "viewer.py"],
        "required": True,
        "restart_delay": 3,
        "max_restarts": 999,
    },
    {
        "name": "monitor",
        "cmd":  [sys.executable, "telegram_monitor.py", "--live"],
        "required": True,
        "restart_delay": 10,
        "max_restarts": 999,
    },
    {
        "name": "ai_agent",
        "cmd":  [sys.executable, "ai_agent.py"],
        "required": False,   # Optional — needs OPENAI_API_KEY
        "restart_delay": 30,
        "max_restarts": 999,
        "needs_env": ["OPENAI_API_KEY"],
    },
]


# ── Process state ──────────────────────────────────────────────────────────────
_procs   = {}    # name -> Popen
_status  = {}    # name -> {running, pid, restarts, last_start, last_crash}
_stop_ev = threading.Event()


def _update_status_file():
    """Write current component status to disk for the web UI to read."""
    try:
        out = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "components": {}
        }
        for name, st in _status.items():
            out["components"][name] = {
                "running": st.get("running", False),
                "pid":     st.get("pid"),
                "restarts": st.get("restarts", 0),
                "last_start": st.get("last_start"),
                "last_crash": st.get("last_crash"),
            }
        STATUS_FILE.write_text(json.dumps(out, indent=2), encoding="utf-8")
    except Exception:
        pass


def _start_component(comp):
    """Start a single component. Returns Popen or None."""
    name = comp["name"]

    # Check required env vars
    for env_var in comp.get("needs_env", []):
        if not os.environ.get(env_var):
            log.warning(f"[{name}] Skipping — {env_var} not set")
            _status[name] = _status.get(name, {})
            _status[name]["running"] = False
            _status[name]["skip_reason"] = f"{env_var} not set"
            return None

    log.info(f"[{name}] Starting: {' '.join(comp['cmd'])}")
    try:
        log_path = BASE_DIR / "telegram_intel" / f"{name}.log"
        log_fh   = open(log_path, "a")
        proc = subprocess.Popen(
            comp["cmd"],
            cwd=str(BASE_DIR),
            env=os.environ.copy(),
            stdout=log_fh,
            stderr=log_fh,
        )
        now = datetime.now(timezone.utc).isoformat()
        _procs[name] = proc
        _status[name] = _status.get(name, {"restarts": 0})
        _status[name].update({"running": True, "pid": proc.pid, "last_start": now})
        _update_status_file()
        log.info(f"[{name}] Started — PID {proc.pid}")
        return proc
    except Exception as e:
        log.error(f"[{name}] Failed to start: {e}")
        _status[name] = _status.get(name, {})
        _status[name]["running"] = False
        return None


def _watch_component(comp):
    """Thread: watch one component and restart if it dies."""
    name = comp["name"]
    _status.setdefault(name, {"restarts": 0})
    _skip_logged = False

    while not _stop_ev.is_set():
        proc = _procs.get(name)
        if proc is None:
            # Check env requirements before attempting start
            missing = [e for e in comp.get("needs_env", []) if not os.environ.get(e)]
            if missing:
                if not _skip_logged:
                    log.info(f"[{name}] Waiting for {', '.join(missing)} — "
                             f"set via admin panel or .env file")
                    _skip_logged = True
                time.sleep(30)
                # Reload .env in case key was added
                loaded = load_env()
                if loaded:
                    _skip_logged = False
                continue
            _skip_logged = False
            # Not started yet — start it
            _start_component(comp)
        else:
            ret = proc.poll()
            if ret is not None:
                # Process died
                now = datetime.now(timezone.utc).isoformat()
                restarts = _status[name].get("restarts", 0) + 1
                _status[name].update({
                    "running": False, "pid": None,
                    "last_crash": now, "restarts": restarts,
                    "exit_code": ret
                })
                _update_status_file()

                if comp.get("required") or os.environ.get("OPENAI_API_KEY"):
                    delay = comp["restart_delay"] * min(restarts, 6)
                    log.warning(f"[{name}] Crashed (exit={ret}, restart #{restarts})"
                                f" — restarting in {delay}s")
                    time.sleep(delay)
                    _procs[name] = None
                    _start_component(comp)

        time.sleep(5)

    # Clean shutdown
    proc = _procs.get(name)
    if proc and proc.poll() is None:
        log.info(f"[{name}] Stopping (PID {proc.pid})…")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _status_printer():
    """Every 60s print a compact health summary to the log."""
    while not _stop_ev.is_set():
        time.sleep(60)
        lines = []
        for name, st in _status.items():
            state = "UP" if st.get("running") else "DOWN"
            pid   = st.get("pid", "-")
            restarts = st.get("restarts", 0)
            lines.append(f"{name}:{state}(pid={pid},restarts={restarts})")
        log.info("HEALTH | " + " | ".join(lines))
        _update_status_file()


def run():
    """Start all components and keep them alive."""
    log.info("=" * 60)
    log.info("ORCHESTRATOR STARTING — Jordan Cyber Intel Platform")
    log.info(f"Base dir: {BASE_DIR}")
    log.info("=" * 60)

    # Load environment
    loaded = load_env()
    if loaded:
        keys = [k for k in loaded if "KEY" in k or "HASH" in k]
        safe = [f"{k}=***" for k in keys] + [f"{k}={v}" for k, v in loaded.items() if k not in keys]
        log.info(f"Loaded .env: {', '.join(safe)}")
    else:
        log.info("No .env file found — using existing environment variables")

    has_ai = bool(os.environ.get("OPENAI_API_KEY"))
    log.info(f"AI agent: {'ENABLED (key found)' if has_ai else 'DISABLED (set OPENAI_API_KEY in .env)'}")

    # Launch watcher threads for each component
    threads = []
    for comp in COMPONENTS:
        t = threading.Thread(
            target=_watch_component,
            args=(comp,),
            name=f"watch-{comp['name']}",
            daemon=True
        )
        t.start()
        threads.append(t)
        time.sleep(1)  # Stagger starts

    # Status printer thread
    sp = threading.Thread(target=_status_printer, daemon=True)
    sp.start()

    log.info("\nAll components launched. Press Ctrl+C to stop.\n")

    def _shutdown(sig, frame):
        log.info("\nShutting down all components…")
        _stop_ev.set()
        time.sleep(3)
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Block main thread
    try:
        while not _stop_ev.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown(None, None)


def print_status():
    """Print current component status."""
    if not STATUS_FILE.exists():
        print("Orchestrator not running (no status file found)")
        return
    data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    print(f"\nSystem Status — {data.get('updated_at','?')}")
    print("-" * 50)
    for name, st in data.get("components", {}).items():
        state  = "● RUNNING" if st.get("running") else "○ DOWN"
        pid    = f"PID={st['pid']}" if st.get("pid") else ""
        rst    = f"restarts={st.get('restarts',0)}"
        crash  = f"last_crash={st.get('last_crash','never')}"
        skip   = f"SKIPPED: {st.get('skip_reason','')}" if not st.get("running") and st.get("skip_reason") else ""
        print(f"  {name:15s} {state:12s} {pid:12s} {rst} {crash} {skip}")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print_status()
    else:
        run()
