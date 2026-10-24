from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Date,
    DateTime, Boolean, Text, UniqueConstraint, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source_url", "event_date", "event_type", name="uq_event"),
    )

    id = Column(Integer, primary_key=True)
    event_type = Column(String(32), nullable=False, default="event")
    title = Column(String(512), nullable=False)
    event_date = Column(Date, nullable=True)
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

    bookmarks = relationship("Bookmark", back_populates="event", cascade="all, delete-orphan")
    hidden_events = relationship("HiddenEvent", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Event {self.title!r} on {self.event_date}>"


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, unique=True)
    chosen_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="bookmarks")

    def __repr__(self):
        return f"<Bookmark event_id={self.event_id}>"


class HiddenEvent(Base):
    __tablename__ = "hidden_events"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="hidden_events")

    def __repr__(self):
        return f"<HiddenEvent event_id={self.event_id}>"


class CustomEvent(Base):
    __tablename__ = "custom_events"

    id = Column(Integer, primary_key=True)
    title = Column(String(512), nullable=False)
    event_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CustomEvent {self.title!r} on {self.event_date}>"


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True)
    endpoint = Column(String(2048), unique=True, nullable=False)
    p256dh = Column(String(512), nullable=False)
    auth = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PushSubscription {self.endpoint[:40]!r}>"


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("push_subscriptions.id"), nullable=False)
    remind_at = Column(DateTime, nullable=False)
    sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Reminder event_id={self.event_id} at={self.remind_at}>"


class ScrapingLog(Base):
    __tablename__ = "scraping_logs"

    id = Column(Integer, primary_key=True)
    source_name = Column(String(256), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False)
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
