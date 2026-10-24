import math
import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import HEADERS, REQUEST_TIMEOUT, REQUEST_DELAY, HOME_LAT, HOME_LNG, MAX_DISTANCE_KM
from models import Event, ScrapingLog, SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points, in km."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def is_nearby(lat: float, lng: float) -> bool:
    """True if the point lies within MAX_DISTANCE_KM of Barneveld."""
    return haversine_km(HOME_LAT, HOME_LNG, lat, lng) <= MAX_DISTANCE_KM


class BaseScraper(ABC):
    # Subclasses set these
    source_name: str = ""
    base_url: str = ""

    def __init__(self):
        self.logger = logging.getLogger(self.source_name or self.__class__.__name__)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> dict:
        log = ScrapingLog(source_name=self.source_name, status="running")
        db = SessionLocal()
        db.add(log)
        db.commit()

        result = {"found": 0, "new": 0, "errors": 0}
        try:
            events = self.parse_events()
            result["found"] = len(events)
            result["new"] = self._save_events(db, events)
            log.status = "success"
            self.logger.info(
                "Done — %d found, %d new.", result["found"], result["new"]
            )
        except Exception as exc:
            log.status = "error"
            log.error_message = str(exc)
            self.logger.exception("Scrape failed: %s", exc)
            result["errors"] = 1
        finally:
            log.finished_at = datetime.utcnow()
            log.events_found = result["found"]
            log.events_new = result["new"]
            db.commit()
            db.close()

        return result

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    @abstractmethod
    def parse_events(self) -> list[dict]:
        """Return a list of dicts with at minimum:
            title (str), source_url (str)
        For events: event_date (date) is required.
        For attractions: omit event_date and set event_type="attraction".
        Optional keys: end_date, location, description, image_url, category, price
        """

    # ------------------------------------------------------------------
    # Helpers available to subclasses
    # ------------------------------------------------------------------

    def fetch_page(self, url: str) -> BeautifulSoup:
        self.logger.info("Fetching %s", url)
        resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return BeautifulSoup(resp.text, "html.parser")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_events(self, db, events: list[dict]) -> int:
        new_count = 0
        for raw in events:
            event_type = raw.get("event_type", "event")
            exists = (
                db.query(Event)
                .filter_by(
                    source_url=raw["source_url"],
                    event_date=raw.get("event_date"),
                    event_type=event_type,
                )
                .first()
            )
            if exists:
                continue

            event = Event(
                source_name=self.source_name,
                event_type=event_type,
                title=raw["title"],
                event_date=raw.get("event_date"),
                end_date=raw.get("end_date"),
                location=raw.get("location"),
                description=raw.get("description"),
                image_url=raw.get("image_url"),
                source_url=raw["source_url"],
                category=raw.get("category"),
                price=raw.get("price"),
                is_active=True,
            )
            db.add(event)
            new_count += 1

        db.commit()
        return new_count
