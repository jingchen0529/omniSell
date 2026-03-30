from __future__ import annotations

import argparse

from app.db.init_db import initialize_database
from app.tasks.queue import build_worker_id, process_next_project_job, run_project_worker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the OmniSell project worker.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one available project job, then exit.",
    )
    parser.add_argument(
        "--worker-id",
        default=None,
        help="Override the worker identifier stored in project jobs.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="Seconds to sleep when no jobs are available.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    initialize_database()

    worker_id = args.worker_id or build_worker_id()
    if args.once:
        process_next_project_job(worker_id=worker_id)
        return

    run_project_worker(worker_id=worker_id, poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
