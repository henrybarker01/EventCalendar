"""
FastAPI server — serves the REST API and (optionally) the Vue frontend.

    python api.py
    # or
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import os
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc, or_
from apscheduler.schedulers.background import BackgroundScheduler
from py_vapid import Vapid
from pywebpush import webpush, WebPushException

from config import DATA_DIR
from enrich import place_for, themes_for
from models import (
    Event, Bookmark, CustomEvent, HiddenEvent, ScrapingLog,
    PushSubscription, Reminder, PlanReminderSent, NewEventsDigest,
    SessionLocal, init_db,
)


# ── VAPID keys ────────────────────────────────────────────────────────

VAPID_KEYS_FILE = os.path.join(DATA_DIR, "vapid_keys.json")
VAPID_CONTACT = "mailto:henry.barker@unexus.nl"


def _load_or_generate_vapid_keys():
    if os.path.exists(VAPID_KEYS_FILE):
        with open(VAPID_KEYS_FILE) as f:
            keys = json.load(f)
        return keys["private_key"], keys["public_key"]

    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    import base64

    priv = ec.generate_private_key(ec.SECP256R1())
    private_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    pub_bytes = priv.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    public_key = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()

    with open(VAPID_KEYS_FILE, "w") as f:
        json.dump({"private_key": private_pem, "public_key": public_key}, f)
    print(f"[EventView] Generated VAPID keys → {VAPID_KEYS_FILE}")
    return private_pem, public_key


VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY = _load_or_generate_vapid_keys()
# webpush() reads a key passed as text with Vapid.from_string, which can't
# parse the PEM stored above (every push failed with "Could not deserialize
# key data"), so hand it the parsed key instead.
VAPID = Vapid.from_pem(VAPID_PRIVATE_KEY.encode())


# ── Reminder scheduler ────────────────────────────────────────────────

LOCAL_TZ = ZoneInfo("Europe/Amsterdam")
NL_WEEKDAYS = ["ma", "di", "wo", "do", "vr", "za", "zo"]
NL_MONTHS = [
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]

# Automatic reminders for everything planned (starred events and own calendar
# items): (days before, title prefix), each at PLAN_REMINDER_TIME local time.
PLAN_REMINDERS = [(5, "Over 5 dagen"), (1, "Morgen")]
PLAN_REMINDER_TIME = time(19, 0)
# A reminder running later than this (e.g. the server was down) is skipped.
PLAN_REMINDER_MAX_DELAY = timedelta(hours=3)


def _nl_date(d: date) -> str:
    return f"{NL_WEEKDAYS[d.weekday()]} {d.day} {NL_MONTHS[d.month - 1]}"


def _push(db, sub: PushSubscription, payload: dict) -> bool:
    """Send one notification. A subscription the push service reports as gone
    (permission revoked, browser data cleared) is deleted."""
    try:
        webpush(
            subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
            data=json.dumps(payload),
            vapid_private_key=VAPID,
            vapid_claims={"sub": VAPID_CONTACT},
        )
        return True
    except Exception as exc:  # also network errors: one device mustn't block the others
        if isinstance(exc, WebPushException) and getattr(exc.response, "status_code", None) in (404, 410):
            db.delete(sub)
        print(f"[EventView] Push to subscription {sub.id} failed: {exc}")
        return False


def _push_all(db, subs: list[PushSubscription], payload: dict) -> tuple[bool, list[PushSubscription]]:
    """Send to every device: (did at least one get it, the devices still registered)."""
    delivered = False
    for sub in subs:
        delivered = _push(db, sub, payload) or delivered
    return delivered, [s for s in subs if s not in db.deleted]


def _send_due_reminders(now: datetime | None = None):
    """Manual 🔔 reminders at a chosen time, sent to every registered device
    like the automatic ones. Retried each minute until a device gets one, for
    up to PLAN_REMINDER_MAX_DELAY."""
    now = now or datetime.utcnow()  # naive UTC, like remind_at
    db = SessionLocal()
    try:
        due = (
            db.query(Reminder)
            .filter(Reminder.remind_at <= now, Reminder.sent == False)  # noqa: E712
            .all()
        )
        subs = db.query(PushSubscription).all() if due else []
        for reminder in due:
            event = db.query(Event).filter_by(id=reminder.event_id).first()
            delivered = False
            if event:
                parts = []
                if event.event_date:
                    parts.append(_nl_date(event.event_date))
                if event.location:
                    parts.append(event.location)
                delivered, subs = _push_all(db, subs, {
                    "title": f"Herinnering: {event.title}",
                    "body": " — ".join(parts),
                    "url": f"/#/events/{event.id}",
                })
            if delivered or not event or now - reminder.remind_at > PLAN_REMINDER_MAX_DELAY:
                reminder.sent = True
        db.commit()
    except Exception as exc:
        print(f"[EventView] _send_due_reminders error: {exc}")
        db.rollback()
    finally:
        db.close()


def _planned_items(db) -> list[dict]:
    """Starred events and own calendar items, with the day they're planned for."""
    items = []
    for b in db.query(Bookmark).all():
        e = b.event
        day = b.chosen_date or e.event_date  # attractions: the day you picked
        if not day:
            continue
        where = e.location or ""
        if not e.is_active:
            where = "⚠️ Niet meer in de agenda van de bron" + (f" · {where}" if where else "")
        items.append({"key": f"event:{e.id}", "title": e.title, "day": day, "where": where,
                      "url": f"/#/events/{e.id}", "planned_at": b.created_at})
    for c in db.query(CustomEvent).all():
        items.append({"key": f"custom:{c.id}", "title": c.title, "day": c.event_date, "where": "",
                      "url": "/#/kalender", "planned_at": c.created_at})
    return items


def _send_plan_reminders(now: datetime | None = None):
    """Automatic reminders for everything planned, sent to every subscribed
    device. Only reminder times after the item was planned count, so starring
    something for tomorrow doesn't fire its "5 days before" straight away.
    One no device received is retried each minute while still in time."""
    now = now or datetime.utcnow()  # naive UTC, like the created_at columns
    db = SessionLocal()
    try:
        subs = db.query(PushSubscription).all()
        if not subs:
            return
        for item in _planned_items(db):
            for days, prefix in PLAN_REMINDERS:
                at = (datetime.combine(item["day"] - timedelta(days=days), PLAN_REMINDER_TIME, LOCAL_TZ)
                      .astimezone(timezone.utc).replace(tzinfo=None))
                if not (item["planned_at"] < at <= now <= at + PLAN_REMINDER_MAX_DELAY):
                    continue
                key = {"item_key": item["key"], "for_date": item["day"], "days_before": days}
                if db.query(PlanReminderSent).filter_by(**key).first():
                    continue
                body = " · ".join(p for p in (_nl_date(item["day"]), item["where"]) if p)
                delivered, subs = _push_all(db, subs, {
                    "title": f"{prefix}: {item['title']}", "body": body, "url": item["url"],
                })
                if delivered:
                    db.add(PlanReminderSent(**key))
                db.commit()
    except Exception as exc:
        print(f"[EventView] _send_plan_reminders error: {exc}")
        db.rollback()
    finally:
        db.close()


def _norm_title(title: str) -> str:
    return re.sub(r"\W+", " ", title.lower()).strip()


def _new_events_since(db, since: datetime) -> list[Event]:
    """Upcoming events added since `since` whose title their source hadn't
    listed before, soonest first. New rows that are just another date of a
    known event (veluwe lists long-running ones date by date, the krant its
    monthly items) don't count."""
    today = datetime.now(LOCAL_TZ).date()
    rows = db.query(Event).filter(Event.event_type == "event").all()
    known = {(e.source_name, _norm_title(e.title)) for e in rows if e.created_at < since}
    new = {}
    for e in sorted(rows, key=lambda e: (e.event_date or date.max, e.id)):
        if e.created_at < since or not e.is_active or not e.event_date or (e.end_date or e.event_date) < today:
            continue
        new.setdefault((e.source_name, _norm_title(e.title)), e)
    return [e for key, e in new.items() if key not in known]


def _send_new_events_digest(now: datetime | None = None):
    """Daily at 18:00: one notification about the events added since the
    previous digest, linking to a page that lists them. Skipped when there's
    nothing new; if no device gets it, the next digest covers these too."""
    now = now or datetime.utcnow()
    db = SessionLocal()
    try:
        last = db.query(NewEventsDigest).order_by(NewEventsDigest.sent_at.desc()).first()
        new = _new_events_since(db, last.sent_at if last else now - timedelta(days=1))
        subs = db.query(PushSubscription).all()
        if not new or not subs:
            return
        digest = NewEventsDigest(sent_at=now, event_ids=json.dumps([e.id for e in new]))
        db.add(digest)
        db.flush()
        n = len(new)
        delivered, _ = _push_all(db, subs, {
            "title": f"{n} nieuwe evenementen" if n > 1 else "1 nieuw evenement",
            "body": ", ".join(e.title for e in new[:3]) + (f" en {n - 3} meer" if n > 3 else ""),
            "url": f"/#/nieuw/{digest.id}",
        })
        if not delivered:
            db.delete(digest)  # keep the window open for the next digest
        db.commit()
    except Exception as exc:
        print(f"[EventView] _send_new_events_digest error: {exc}")
        db.rollback()
    finally:
        db.close()


_scheduler = BackgroundScheduler()
_scheduler.add_job(_send_due_reminders, "interval", minutes=1)
_scheduler.add_job(_send_plan_reminders, "interval", minutes=1)
# Survives a restart around 18:00 (misfire grace) without sending twice (coalesce).
_scheduler.add_job(_send_new_events_digest, "cron", hour=18, minute=0, timezone="Europe/Amsterdam",
                   misfire_grace_time=3600, coalesce=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _scheduler.start()
    yield
    _scheduler.shutdown()


app = FastAPI(title="EventView API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic response schemas ─────────────────────────────────────────

class EventOut(BaseModel):
    id: int
    event_type: str
    title: str
    event_date: date | None
    end_date: date | None
    location: str | None
    description: str | None
    image_url: str | None
    source_url: str
    source_name: str
    category: str | None
    price: str | None
    is_active: bool
    is_bookmarked: bool = False
    bookmark_date: date | None = None
    is_hidden: bool = False
    # Derived for the UI's filters (see enrich.py), not stored.
    themes: list[str] = []
    town: str | None = None
    municipality: str | None = None
    distance_km: float | None = None

    class Config:
        from_attributes = True


def _event_out(e: Event) -> EventOut:
    out = EventOut.model_validate(e)
    out.themes = themes_for(e.title, e.category)
    place = place_for(e.location, e.title, e.source_name)
    if place:
        out.town, out.municipality, out.distance_km = place
    return out


class BookmarkOut(BaseModel):
    id: int
    event_id: int
    chosen_date: date | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CustomEventOut(BaseModel):
    id: int
    title: str
    event_date: date
    created_at: datetime

    class Config:
        from_attributes = True


class CustomEventIn(BaseModel):
    title: str
    event_date: date


class ScrapingLogOut(BaseModel):
    id: int
    source_name: str
    status: str
    events_found: int
    events_new: int
    error_message: str | None

    class Config:
        from_attributes = True


class PushSubscriptionData(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class ReminderIn(BaseModel):
    event_id: int
    remind_at: datetime
    subscription: PushSubscriptionData


class ReminderOut(BaseModel):
    id: int
    event_id: int
    remind_at: datetime
    sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Routes ────────────────────────────────────────────────────────────

@app.get("/api/events", response_model=list[EventOut])
def list_events(
    source: str | None = Query(None),
    event_type: str | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(100, le=5000),
    offset: int = Query(0),
):
    db = SessionLocal()
    try:
        q = db.query(Event)
        if active_only:
            # Starred events stay listed after their source drops them, so the
            # card can say so instead of the plan silently disappearing.
            q = q.filter(or_(Event.is_active == True, Event.bookmarks.any()))
        if source:
            q = q.filter(Event.source_name == source)
        if event_type:
            q = q.filter(Event.event_type == event_type)
        if from_date:
            # Multi-day events still running on from_date count too.
            q = q.filter(or_(Event.event_date >= from_date, Event.end_date >= from_date))
        if to_date:
            q = q.filter(Event.event_date <= to_date)
        events = q.order_by(Event.event_date).offset(offset).limit(limit).all()
        bookmarks_map = {b.event_id: b for b in db.query(Bookmark).all()}
        hidden_set = {h.event_id for h in db.query(HiddenEvent).all()}
        result = []
        for e in events:
            d = _event_out(e)
            if e.id in bookmarks_map:
                d.is_bookmarked = True
                d.bookmark_date = bookmarks_map[e.id].chosen_date
            if e.id in hidden_set:
                d.is_hidden = True
            result.append(d)
        return result
    finally:
        db.close()


@app.get("/api/events/{event_id}", response_model=EventOut)
def get_event(event_id: int):
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        out = _event_out(event)
        bookmark = db.query(Bookmark).filter_by(event_id=event_id).first()
        if bookmark:
            out.is_bookmarked = True
            out.bookmark_date = bookmark.chosen_date
        if db.query(HiddenEvent).filter_by(event_id=event_id).first():
            out.is_hidden = True
        return out
    finally:
        db.close()


class DigestOut(BaseModel):
    id: int
    sent_at: datetime
    events: list[EventOut]


def _digest_out(db, d: NewEventsDigest) -> DigestOut:
    """The digest's events that still exist (old rows get pruned), with the
    same starred/hidden flags as /api/events."""
    ids = json.loads(d.event_ids)
    by_id = {e.id: e for e in db.query(Event).filter(Event.id.in_(ids))}
    bookmarks = {b.event_id: b for b in db.query(Bookmark).filter(Bookmark.event_id.in_(ids))}
    hidden = {h.event_id for h in db.query(HiddenEvent).filter(HiddenEvent.event_id.in_(ids))}
    events = []
    for i in ids:
        if i not in by_id:
            continue
        out = _event_out(by_id[i])
        if i in bookmarks:
            out.is_bookmarked = True
            out.bookmark_date = bookmarks[i].chosen_date
        out.is_hidden = i in hidden
        events.append(out)
    return DigestOut(id=d.id, sent_at=d.sent_at.replace(tzinfo=timezone.utc), events=events)


@app.get("/api/digests/latest", response_model=DigestOut)
def latest_digest():
    db = SessionLocal()
    try:
        d = db.query(NewEventsDigest).order_by(NewEventsDigest.sent_at.desc()).first()
        if not d:
            raise HTTPException(status_code=404, detail="No new-events digest yet")
        return _digest_out(db, d)
    finally:
        db.close()


@app.get("/api/digests/{digest_id}", response_model=DigestOut)
def get_digest(digest_id: int):
    db = SessionLocal()
    try:
        d = db.get(NewEventsDigest, digest_id)
        if not d:
            raise HTTPException(status_code=404, detail="Digest not found")
        return _digest_out(db, d)
    finally:
        db.close()


@app.get("/api/sources")
def list_sources():
    db = SessionLocal()
    try:
        rows = db.query(Event.source_name).distinct().all()
        return [r[0] for r in rows]
    finally:
        db.close()


@app.get("/api/bookmarks", response_model=list[EventOut])
def list_bookmarks():
    db = SessionLocal()
    try:
        bookmarks = db.query(Bookmark).order_by(Bookmark.created_at).all()
        result = []
        for b in bookmarks:
            out = _event_out(b.event)
            out.is_bookmarked = True
            out.bookmark_date = b.chosen_date
            result.append(out)
        return result
    finally:
        db.close()


@app.post("/api/bookmarks/{event_id}", response_model=BookmarkOut)
def add_bookmark(event_id: int, chosen_date: date | None = Query(None)):
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        existing = db.query(Bookmark).filter_by(event_id=event_id).first()
        if existing:
            if chosen_date is not None and existing.chosen_date != chosen_date:
                existing.chosen_date = chosen_date
                db.commit()
                db.refresh(existing)
            return existing
        bookmark = Bookmark(event_id=event_id, chosen_date=chosen_date)
        db.add(bookmark)
        db.commit()
        db.refresh(bookmark)
        return bookmark
    finally:
        db.close()


@app.delete("/api/bookmarks/{event_id}")
def remove_bookmark(event_id: int):
    db = SessionLocal()
    try:
        bookmark = db.query(Bookmark).filter_by(event_id=event_id).first()
        if not bookmark:
            raise HTTPException(status_code=404, detail="Bookmark not found")
        db.delete(bookmark)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.post("/api/hidden/{event_id}")
def hide_event(event_id: int):
    db = SessionLocal()
    try:
        if not db.query(Event).filter(Event.id == event_id).first():
            raise HTTPException(status_code=404, detail="Event not found")
        if not db.query(HiddenEvent).filter_by(event_id=event_id).first():
            db.add(HiddenEvent(event_id=event_id))
            db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.delete("/api/hidden/{event_id}")
def unhide_event(event_id: int):
    db = SessionLocal()
    try:
        h = db.query(HiddenEvent).filter_by(event_id=event_id).first()
        if h:
            db.delete(h)
            db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.get("/api/custom-events", response_model=list[CustomEventOut])
def list_custom_events():
    db = SessionLocal()
    try:
        return db.query(CustomEvent).order_by(CustomEvent.event_date).all()
    finally:
        db.close()


@app.post("/api/custom-events", response_model=CustomEventOut)
def create_custom_event(body: CustomEventIn):
    db = SessionLocal()
    try:
        ev = CustomEvent(title=body.title, event_date=body.event_date)
        db.add(ev)
        db.commit()
        db.refresh(ev)
        return ev
    finally:
        db.close()


@app.delete("/api/custom-events/{event_id}")
def delete_custom_event(event_id: int):
    db = SessionLocal()
    try:
        ev = db.query(CustomEvent).filter(CustomEvent.id == event_id).first()
        if not ev:
            raise HTTPException(status_code=404, detail="Custom event not found")
        db.delete(ev)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.get("/api/logs", response_model=list[ScrapingLogOut])
def list_logs(limit: int = Query(50, le=200)):
    db = SessionLocal()
    try:
        return (
            db.query(ScrapingLog)
            .order_by(desc(ScrapingLog.started_at))
            .limit(limit)
            .all()
        )
    finally:
        db.close()


@app.get("/api/image-proxy")
async def image_proxy(url: str = Query(...)):
    """Fetch a remote image server-side to avoid hotlink blocking."""
    allowed_hosts = ["visitregiobarneveld.nl", "app.thefeedfactory.nl", "www.wattedoenin.nl", "storage.pubble.nl"]
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if not any(host.endswith(h) for h in allowed_hosts):
        raise HTTPException(status_code=400, detail="Host not allowed")

    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Image fetch failed")
        content_type = resp.headers.get("content-type", "image/jpeg")
        return StreamingResponse(iter([resp.content]), media_type=content_type)


@app.post("/api/scrape/{source_name}")
def trigger_scrape(source_name: str):
    """Manually trigger a scraper run via the API."""
    from main import SCRAPERS, run_scraper
    if source_name not in SCRAPERS:
        raise HTTPException(status_code=404, detail=f"Unknown scraper '{source_name}'")
    result = run_scraper(source_name)
    return result


# ── Push notification routes ──────────────────────────────────────────

@app.get("/api/push/vapid-key")
def get_vapid_key():
    return {"public_key": VAPID_PUBLIC_KEY}


def _upsert_subscription(db, data: PushSubscriptionData) -> PushSubscription:
    sub = db.query(PushSubscription).filter_by(endpoint=data.endpoint).first()
    if sub:
        sub.p256dh = data.p256dh
        sub.auth = data.auth
    else:
        sub = PushSubscription(endpoint=data.endpoint, p256dh=data.p256dh, auth=data.auth)
        db.add(sub)
        db.flush()
    return sub


@app.post("/api/push/subscriptions")
def register_push_subscription(body: PushSubscriptionData):
    """Register a device; automatic reminders for planned items go to all of them."""
    db = SessionLocal()
    try:
        _upsert_subscription(db, body)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.post("/api/push/test")
def send_test_push():
    """Send a test notification to every registered device."""
    db = SessionLocal()
    try:
        subs = db.query(PushSubscription).all()
        sent = sum(_push(db, s, {"title": "EventView", "body": "Meldingen werken 🎉", "url": "/#/"}) for s in subs)
        db.commit()
        return {"devices": sent}
    finally:
        db.close()


@app.get("/api/reminders", response_model=list[ReminderOut])
def list_reminders():
    db = SessionLocal()
    try:
        return (
            db.query(Reminder)
            .filter(Reminder.sent == False)  # noqa: E712
            .all()
        )
    finally:
        db.close()


@app.post("/api/reminders", response_model=ReminderOut)
def create_reminder(body: ReminderIn):
    db = SessionLocal()
    try:
        if not db.query(Event).filter(Event.id == body.event_id).first():
            raise HTTPException(status_code=404, detail="Event not found")

        sub = _upsert_subscription(db, body.subscription)

        reminder = db.query(Reminder).filter_by(event_id=body.event_id).first()
        if reminder:
            reminder.subscription_id = sub.id
            reminder.remind_at = body.remind_at
            reminder.sent = False
        else:
            reminder = Reminder(
                event_id=body.event_id,
                subscription_id=sub.id,
                remind_at=body.remind_at,
            )
            db.add(reminder)

        db.commit()
        db.refresh(reminder)
        return reminder
    finally:
        db.close()


@app.delete("/api/reminders/{reminder_id}")
def delete_reminder(reminder_id: int):
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")
        db.delete(reminder)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


# ── Serve Vue frontend (if built) ─────────────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "EventView.UI", "dist")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/sw.js", include_in_schema=False)
    def serve_sw():
        sw_path = os.path.join(FRONTEND_DIR, "sw.js")
        if os.path.isfile(sw_path):
            return FileResponse(sw_path, media_type="application/javascript")
        raise HTTPException(status_code=404, detail="sw.js not found")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ── Dev entry point ───────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
