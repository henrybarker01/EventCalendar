from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Date,
    DateTime, Boolean, Text, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        # Attractions have no date, so deduplicate by source_url + event_type
        UniqueConstraint("source_url", "event_date", "event_type", name="uq_event"),
    )

    id = Column(Integer, primary_key=True)
    # "event" = time-bound event, "attraction" = permanent thing to do
    event_type = Column(String(32), nullable=False, default="event")
    title = Column(String(512), nullable=False)
    event_date = Column(Date, nullable=True)   # null for attractions
    end_date = Column(Date, nullable=True)
    location = Column(String(512), nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(1024), nullable=True)
    source_url = Column(String(1024), nullable=False)
    source_name = Column(String(256), nullable=False)
    category = Column(String(256), nullable=True)
    price = Column(String(128), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Event {self.title!r} on {self.event_date}>"


class ScrapingLog(Base):
    __tablename__ = "scraping_logs"

    id = Column(Integer, primary_key=True)
    source_name = Column(String(256), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False)  # success | error | partial
    events_found = Column(Integer, default=0)
    events_new = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<ScrapingLog {self.source_name} {self.status}>"


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    Base.metadata.create_all(engine)
    print("Database initialised.")
