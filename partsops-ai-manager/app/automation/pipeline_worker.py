"""DB-lease worker for durable Kanban pipeline runs."""
from __future__ import annotations

import argparse
import os
import socket
import time

from services.pipeline_runs import run_once


def main() -> None:
    parser = argparse.ArgumentParser(description="PartsOps durable pipeline worker")
    parser.add_argument("--once", action="store_true", help="claim and execute a single queued run")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    worker_id = os.getenv("PARTSOPS_PIPELINE_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
    while True:
        result = run_once(worker_id)
        if args.once:
            return
        if result is None:
            time.sleep(max(0.1, args.poll_seconds))


if __name__ == "__main__":
    main()
