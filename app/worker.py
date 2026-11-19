"""The background worker: keeps prices fresh and builds the "Barney noticed" feed without anyone opening the app.

Run it as its own process, so a busy web server never slows it down and a restart of the web server never stops it:

    python -m app.worker              # loops forever, every WORKER_INTERVAL_MINUTES (default 360)
    python -m app.worker --once       # one pass, for a cron job or a scheduled task

Set ALERTS=off on the web server when this runs separately, so the two do not both check prices.
"""
import logging
import os
import sys
import time

from app import feed

log = logging.getLogger("barney.worker")


def run_once() -> dict:
    result = feed.build_all()
    log.info("worker pass: %s", result)
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    if "--once" in sys.argv:
        run_once()
        return
    every = int(os.getenv("WORKER_INTERVAL_MINUTES", "360")) * 60
    while True:
        try:
            run_once()
        except Exception:
            log.exception("worker pass failed")
        time.sleep(every)


if __name__ == "__main__":
    main()
