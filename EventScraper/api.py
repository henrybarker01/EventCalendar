"""
FastAPI server — serves the REST API and (optionally) the Vue frontend.

    python api.py
    # or
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime

import httpx
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc
from apscheduler.schedulers.background import BackgroundScheduler
from pywebpush import webpush, WebPushException

from config import DATA_DIR
from models import (
    Event, Bookmark, CustomEvent, HiddenEvent, ScrapingLog,
    PushSubscription, Reminder,
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


# ── Reminder scheduler ────────────────────────────────────────────────

def _send_due_reminders():
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        due = (
            db.query(Reminder)
            .filter(Reminder.remind_at <= now, Reminder.sent == False)  # noqa: E712
            .all()
        )
        for reminder in due:
            sub = db.query(PushSubscription).filter_by(id=reminder.subscription_id).first()
            event = db.query(Event).filter_by(id=reminder.event_id).first()
            if sub and event:
                parts = []
                if event.event_date:
                    parts.append(f"{event.event_date.day} {event.event_date.strftime('%B')}")
                if event.location:
                    parts.append(event.location)
                try:
                    webpush(
                        subscription_info={
                            "endpoint": sub.endpoint,
                            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                        },
                        data=json.dumps({
                            "title": f"Herinnering: {event.title}",
                            "body": " — ".join(parts) if parts else "",
                            "url": f"/#/events/{event.id}",
                        }),
                        vapid_private_key=VAPID_PRIVATE_KEY,
                        vapid_claims={"sub": VAPID_CONTACT},
                    )
                except WebPushException as exc:
                    print(f"[EventView] Push failed for reminder {reminder.id}: {exc}")
            reminder.sent = True
        db.commit()
    except Exception as exc:
        print(f"[EventView] _send_due_reminders error: {exc}")
        db.rollback()
    finally:
        db.close()


_scheduler = BackgroundScheduler()
_scheduler.add_job(_send_due_reminders, "interval", minutes=1)


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

    class Config:
        from_attributes = True


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
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    db = SessionLocal()
    try:
        q = db.query(Event)
        if active_only:
            q = q.filter(Event.is_active == True)
        if source:
            q = q.filter(Event.source_name == source)
        if event_type:
            q = q.filter(Event.event_type == event_type)
        if from_date:
            q = q.filter(Event.event_date >= from_date)
        if to_date:
            q = q.filter(Event.event_date <= to_date)
        events = q.order_by(Event.event_date).offset(offset).limit(limit).all()
        bookmarks_map = {b.event_id: b for b in db.query(Bookmark).all()}
        hidden_set = {h.event_id for h in db.query(HiddenEvent).all()}
        result = []
        for e in events:
            d = EventOut.model_validate(e)
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
        out = EventOut.model_validate(event)
        bookmark = db.query(Bookmark).filter_by(event_id=event_id).first()
        if bookmark:
            out.is_bookmarked = True
            out.bookmark_date = bookmark.chosen_date
        if db.query(HiddenEvent).filter_by(event_id=event_id).first():
            out.is_hidden = True
        return out
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
            out = EventOut.model_validate(b.event)
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
    allowed_hosts = ["visitregiobarneveld.nl", "app.thefeedfactory.nl", "www.wattedoenin.nl"]
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

        sub = db.query(PushSubscription).filter_by(endpoint=body.subscription.endpoint).first()
        if sub:
            sub.p256dh = body.subscription.p256dh
            sub.auth = body.subscription.auth
        else:
            sub = PushSubscription(
                endpoint=body.subscription.endpoint,
                p256dh=body.subscription.p256dh,
                auth=body.subscription.auth,
            )
            db.add(sub)
            db.flush()

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
