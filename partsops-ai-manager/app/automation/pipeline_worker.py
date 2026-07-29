"""DB-lease worker for durable Kanban pipeline runs."""
from __future__ import annotations

import argparse
import fcntl
import os
import socket
import time
from pathlib import Path

from services.pipeline_runs import run_once


def _acquire_worker_lock() -> object | None:
    """Allow only one queue consumer per checkout/database."""
    lock_path = Path(os.getenv("PARTSOPS_PIPELINE_WORKER_LOCK", ".pipeline_worker.lock"))
    lock_file = lock_path.open("a+")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return None
    return lock_file


def main() -> None:
    parser = argparse.ArgumentParser(description="PartsOps durable pipeline worker")
    parser.add_argument("--once", action="store_true", help="claim and execute a single queued run")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    lock_file = _acquire_worker_lock()
    if lock_file is None:
        print("Pipeline worker already running; exiting.", flush=True)
        return
    worker_id = os.getenv("PARTSOPS_PIPELINE_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    try:
        while True:
            result = run_once(worker_id)
            if args.once:
                return
            if result is None:
                time.sleep(max(0.1, args.poll_seconds))
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


if __name__ == "__main__":
    main()
