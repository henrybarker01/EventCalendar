"""
Entry point for scraping and database management.

Usage:
    python main.py --init-db
    python main.py --scraper barneveld
    python main.py --all
    python main.py --schedule          # Run all scrapers on a daily cron via APScheduler
    python main.py --prune             # Delete old rows now (also runs after every --all)
"""

import argparse
import logging
import sys
import time
from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from config import KEEP_PAST_DAYS
from models import Bookmark, Event, HiddenEvent, PlanReminderSent, Reminder, ScrapingLog, SessionLocal, init_db
from scrapers.barneveld_centrum import BarneveldCentrumScraper
from scrapers.barneveldse_krant import BarneveldseKrantScraper
from scrapers.veluwe_nl import VeluweNlScraper
from scrapers.wattedoenin_nl import WattedoeninNlScraper

# ── Scraper registry ──────────────────────────────────────────────────
# Maps CLI name → scraper class. Add new scrapers here.
SCRAPERS: dict[str, type] = {
    "barneveld": BarneveldCentrumScraper,
    "veluwe": VeluweNlScraper,
    "wattedoenin": WattedoeninNlScraper,
    "barneveldsekrant": BarneveldseKrantScraper,
}

logger = logging.getLogger("main")


def run_scraper(name: str) -> dict:
    cls = SCRAPERS.get(name)
    if cls is None:
        print(f"Unknown scraper '{name}'. Available: {', '.join(SCRAPERS)}")
        sys.exit(1)
    return cls().run()


def run_all() -> None:
    for name in SCRAPERS:
        print(f"\n── {name} ──")
        result = run_scraper(name)
        print(f"   found={result['found']}  new={result['new']}  retired={result['retired']}  errors={result['errors']}")
    prune_old_rows()


def prune_old_rows() -> None:
    """Delete events that ended more than KEEP_PAST_DAYS ago, with their
    hidden/reminder rows, and scraping logs of that age. Starred events are
    kept: they're the record of what you planned."""
    cutoff = date.today() - timedelta(days=KEEP_PAST_DAYS)
    db = SessionLocal()
    try:
        old_ids = [i for (i,) in db.query(Event.id).filter(
            Event.event_date.isnot(None),
            func.coalesce(Event.end_date, Event.event_date) < cutoff,
            Event.id.notin_(select(Bookmark.event_id)),
        )]
        # Bulk deletes skip the ORM cascades, so remove dependent rows first.
        for start in range(0, len(old_ids), 500):
            chunk = old_ids[start:start + 500]
            for model in (HiddenEvent, Reminder):
                db.query(model).filter(model.event_id.in_(chunk)).delete(synchronize_session=False)
            db.query(Event).filter(Event.id.in_(chunk)).delete(synchronize_session=False)
        logs = db.query(ScrapingLog).filter(
            ScrapingLog.started_at < datetime.utcnow() - timedelta(days=KEEP_PAST_DAYS)
        ).delete(synchronize_session=False)
        db.query(PlanReminderSent).filter(PlanReminderSent.for_date < cutoff).delete(synchronize_session=False)
        db.commit()
        print(f"\nPruned {len(old_ids)} events that ended before {cutoff} and {logs} scraping logs.")
    finally:
        db.close()


def start_scheduler(interval_hours: float = 24.0) -> None:
    """Keep the process alive and run all scrapers on a schedule."""
    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler()
    scheduler.add_job(run_all, "interval", hours=interval_hours, id="scrape_all")
    print(f"Scheduler started — running every {interval_hours}h. Ctrl-C to stop.")

    # Run immediately on start so we don't wait the first interval
    run_all()

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("Scheduler stopped.")


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="EventView scraper CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init-db", action="store_true", help="Initialise the SQLite database")
    group.add_argument("--scraper", metavar="NAME", help="Run a single scraper by name")
    group.add_argument("--all", action="store_true", help="Run all registered scrapers once")
    group.add_argument(
        "--prune",
        action="store_true",
        help=f"Delete events that ended over {KEEP_PAST_DAYS} days ago (keeps starred ones)",
    )
    group.add_argument(
        "--schedule",
        nargs="?",
        const=24.0,
        type=float,
        metavar="HOURS",
        help="Run all scrapers on a schedule (default: every 24 h)",
    )

    args = parser.parse_args()

    if args.init_db:
        init_db()
    elif args.scraper:
        result = run_scraper(args.scraper)
        print(f"found={result['found']}  new={result['new']}  retired={result['retired']}  errors={result['errors']}")
    elif args.all:
        run_all()
    elif args.prune:
        prune_old_rows()
    elif args.schedule is not None:
        start_scheduler(interval_hours=args.schedule)


if __name__ == "__main__":
    main()
