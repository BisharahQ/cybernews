#!/usr/bin/env python3
"""
CYBERNEWS DAEMON ORCHESTRATOR
==============================
Launches and keeps alive all three services:
  1. telegram_monitor.py --live    — live message collection
  2. channel_discovery.py --daemon — periodic channel discovery
  3. viewer.py                     — web UI

Each service is restarted automatically if it crashes.
Press Ctrl+C to shut everything down cleanly.

Usage:
  python run_all.py               # Start all services
  python run_all.py --no-viewer   # Start monitor + discovery only (headless)
"""

import sys
import time
import signal
import logging
import subprocess
import threading
from pathlib import Path
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
PYTHON         = sys.executable
RESTART_DELAY  = 10   # seconds before restarting a crashed service
LOG_DIR        = BASE_DIR / "telegram_intel"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ORCHESTRATOR] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "orchestrator.log", encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("Orchestrator")

# ── Service definitions ──────────────────────────────────────────────────────
SERVICES = [
    {
        "name":    "monitor",
        "cmd":     [PYTHON, str(BASE_DIR / "telegram_monitor.py"), "--live"],
        "log":     LOG_DIR / "monitor_stdout.log",
        "enabled": True,
    },
    {
        "name":    "discovery",
        "cmd":     [PYTHON, str(BASE_DIR / "channel_discovery.py"), "--daemon", "--interval", "8"],
        "log":     LOG_DIR / "discovery_stdout.log",
        "enabled": True,
    },
    {
        "name":    "viewer",
        "cmd":     [PYTHON, str(BASE_DIR / "viewer.py")],
        "log":     LOG_DIR / "viewer_stdout.log",
        "enabled": "--no-viewer" not in sys.argv,
    },
]

# ── Global state ─────────────────────────────────────────────────────────────
_procs: dict[str, subprocess.Popen] = {}
_stop_event = threading.Event()


def _launch(service: dict) -> subprocess.Popen:
    """Start a single service subprocess, tee-ing stdout/stderr to its log file."""
    log_fh = open(service["log"], "a", encoding="utf-8", buffering=1)
    log_fh.write(f"\n\n{'='*60}\n"
                 f"STARTED {service['name']} at {datetime.now().isoformat()}\n"
                 f"CMD: {' '.join(service['cmd'])}\n"
                 f"{'='*60}\n")
    log_fh.flush()
    proc = subprocess.Popen(
        service["cmd"],
        stdout=log_fh,
        stderr=log_fh,
        cwd=str(BASE_DIR),
        # Use a new process group so Ctrl+C doesn't kill children before we do
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    log.info(f"[{service['name']}] started  (PID {proc.pid})")
    return proc


def _supervise(service: dict):
    """Thread: keeps a service running until _stop_event is set."""
    while not _stop_event.is_set():
        proc = _launch(service)
        _procs[service["name"]] = proc

        while not _stop_event.is_set():
            try:
                proc.wait(timeout=2)
                break  # process exited — fall through to restart logic
            except subprocess.TimeoutExpired:
                continue

        if _stop_event.is_set():
            # Graceful shutdown requested — terminate the process
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            log.info(f"[{service['name']}] stopped")
            return

        rc = proc.returncode
        log.warning(f"[{service['name']}] exited with code {rc}. "
                    f"Restarting in {RESTART_DELAY}s...")
        _stop_event.wait(timeout=RESTART_DELAY)


def _shutdown(signum=None, frame=None):
    log.info("Shutdown signal received — stopping all services...")
    _stop_event.set()


def main():
    # Register shutdown handler
    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    active_services = [s for s in SERVICES if s["enabled"]]
    log.info("="*60)
    log.info("CYBERNEWS DAEMON ORCHESTRATOR - STARTING")
    log.info(f"Services: {[s['name'] for s in active_services]}")
    log.info(f"Base dir: {BASE_DIR}")
    log.info("="*60)

    threads = []
    for svc in active_services:
        t = threading.Thread(target=_supervise, args=(svc,), daemon=True, name=svc["name"])
        t.start()
        threads.append(t)
        time.sleep(2)  # stagger starts to avoid auth race conditions

    log.info("All services launched. Press Ctrl+C to stop.\n")
    if any(s["name"] == "viewer" and s["enabled"] for s in active_services):
        log.info("Web UI → http://localhost:5000\n")

    # Wait for stop event (Ctrl+C / SIGTERM)
    _stop_event.wait()

    log.info("Waiting for threads to finish...")
    for t in threads:
        t.join(timeout=15)

    log.info("Orchestrator shutdown complete.")


if __name__ == "__main__":
    main()
