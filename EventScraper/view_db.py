"""
Interactive CLI database viewer.

    python view_db.py              # browse events
    python view_db.py --logs       # show scraping logs
    python view_db.py --export     # export events to events.csv
"""

import argparse
import csv
import sys

from models import Event, ScrapingLog, SessionLocal, init_db


def view_events(db):
    events = db.query(Event).order_by(Event.event_date).all()
    if not events:
        print("No events in database.")
        return
    print(f"\n{'ID':>4}  {'DATE':<12}  {'SOURCE':<14}  TITLE")
    print("-" * 72)
    for e in events:
        status = "" if e.is_active else " [inactive]"
        print(f"{e.id:>4}  {str(e.event_date):<12}  {e.source_name:<14}  {e.title}{status}")
    print(f"\nTotal: {len(events)} events")


def view_logs(db):
    logs = db.query(ScrapingLog).order_by(ScrapingLog.started_at.desc()).limit(50).all()
    if not logs:
        print("No scraping logs.")
        return
    print(f"\n{'ID':>4}  {'STARTED':<20}  {'SOURCE':<16}  {'STATUS':<10}  FOUND  NEW")
    print("-" * 72)
    for l in logs:
        started = str(l.started_at)[:19] if l.started_at else "-"
        print(
            f"{l.id:>4}  {started:<20}  {l.source_name:<16}  "
            f"{l.status:<10}  {l.events_found:>5}  {l.events_new:>3}"
        )
        if l.error_message:
            print(f"       ERROR: {l.error_message}")


def export_csv(db, path="events.csv"):
    events = db.query(Event).order_by(Event.event_date).all()
    fields = [
        "id", "title", "event_date", "end_date", "location",
        "description", "source_url", "source_name", "category",
        "price", "is_active",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for e in events:
            writer.writerow({k: getattr(e, k) for k in fields})
    print(f"Exported {len(events)} events to {path}")


def main():
    parser = argparse.ArgumentParser(description="EventView database viewer")
    parser.add_argument("--logs", action="store_true", help="Show scraping logs")
    parser.add_argument("--export", action="store_true", help="Export events to CSV")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        if args.logs:
            view_logs(db)
        elif args.export:
            export_csv(db)
        else:
            view_events(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
