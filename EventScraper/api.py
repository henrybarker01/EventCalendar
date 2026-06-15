"""
FastAPI server — serves the REST API and (optionally) the Vue frontend.

    python api.py
    # or
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import os
from datetime import date

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import desc

from models import Event, ScrapingLog, SessionLocal, init_db

app = FastAPI(title="EventView API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic response schemas ─────────────────────────────────────────

class EventOut(BaseModel):
    id: int
    title: str
    event_date: date
    end_date: date | None
    location: str | None
    description: str | None
    image_url: str | None
    source_url: str
    source_name: str
    category: str | None
    price: str | None
    is_active: bool

    class Config:
        from_attributes = True


class ScrapingLogOut(BaseModel):
    id: int
    source_name: str
    status: str
    events_found: int
    events_new: int
    error_message: str | None

    class Config:
        from_attributes = True


# ── Routes ────────────────────────────────────────────────────────────

@app.get("/api/events", response_model=list[EventOut])
def list_events(
    source: str | None = Query(None),
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
        if from_date:
            q = q.filter(Event.event_date >= from_date)
        if to_date:
            q = q.filter(Event.event_date <= to_date)
        return q.order_by(Event.event_date).offset(offset).limit(limit).all()
    finally:
        db.close()


@app.get("/api/events/{event_id}", response_model=EventOut)
def get_event(event_id: int):
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        return event
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


@app.post("/api/scrape/{source_name}")
def trigger_scrape(source_name: str):
    """Manually trigger a scraper run via the API."""
    import importlib, sys
    # lazy import to avoid circular deps
    from main import SCRAPERS, run_scraper
    if source_name not in SCRAPERS:
        raise HTTPException(status_code=404, detail=f"Unknown scraper '{source_name}'")
    result = run_scraper(source_name)
    return result


# ── Serve Vue frontend (if built) ─────────────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "EventViewer", "dist")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ── Dev entry point ───────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    init_db()
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
