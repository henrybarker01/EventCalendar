"""
Scraper for visitregiobarneveld.nl/agenda/

Card structure (as of June 2026):
    <div class="card position-relative">
      <div class="card-img-wrapper"><img class="card-img-top ..."></div>
      <div class="card-tags"><span class="badge">Category</span></div>
      <div class="card-content">
        <h3 class="h5">Title</h3>
        <p class="card-text">Short description</p>
        <p class="card-date">Za 20 jun 2026</p>          ← single date
        <p class="card-date">Di 14 jul - Di 18 aug 2026</p>  ← date range
      </div>
      <a class="clickable" href="...full event URL..."></a>
    </div>

Cards without a card-date element are permanent attractions (museums, parks,
walking routes, etc.) — not time-bound events. They are skipped.
"""

import re
from datetime import date

from dateutil import parser as dateparser

from base_scraper import BaseScraper

NL_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}

NL_DAY_PREFIX = re.compile(
    r"^(ma|di|wo|do|vr|za|zo|maandag|dinsdag|woensdag|donderdag|"
    r"vrijdag|zaterdag|zondag)\s+",
    re.IGNORECASE,
)

DATE_RANGE_SEP = re.compile(r"\s*-\s*")


def _normalise(text: str) -> str:
    """Strip Dutch day prefix and replace Dutch month names with numbers."""
    text = NL_DAY_PREFIX.sub("", text.strip())
    for nl, num in NL_MONTHS.items():
        text = re.sub(rf"\b{nl}\b", str(num), text, flags=re.IGNORECASE)
    return text


def _parse_dutch_date(text: str) -> date | None:
    if not text:
        return None
    try:
        return dateparser.parse(_normalise(text), dayfirst=True).date()
    except Exception:
        return None


def _parse_date_range(raw: str) -> tuple[date | None, date | None]:
    """
    Parse single dates and ranges like 'Di 14 jul 2026 - Di 18 aug 2026'.
    Returns (start_date, end_date). end_date is None for single dates.
    """
    parts = DATE_RANGE_SEP.split(raw, maxsplit=1)
    if len(parts) == 2:
        start = _parse_dutch_date(parts[0])
        end = _parse_dutch_date(parts[1])
        # If end date parsed but start didn't get a year, borrow end's year
        if start and end and start.year != end.year and start < end:
            pass  # dateutil already handled it correctly
        return start, end
    return _parse_dutch_date(parts[0]), None


class BarneveldCentrumScraper(BaseScraper):
    source_name = "barneveld"
    base_url = "https://visitregiobarneveld.nl/agenda/"

    def parse_events(self) -> list[dict]:
        soup = self.fetch_page(self.base_url)
        cards = soup.select("div.card.position-relative")
        self.logger.info("Found %d cards total.", len(cards))

        events = []
        skipped = 0
        for card in cards:
            event = self._parse_card(card)
            if event:
                events.append(event)
            else:
                skipped += 1

        self.logger.info("Kept %d events, skipped %d attractions.", len(events), skipped)
        return events

    def _parse_card(self, card) -> dict | None:
        title_el = card.select_one("h3, h2")
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None

        # No date element → permanent attraction, not a time-bound event
        date_el = card.select_one("p.card-date")
        if not date_el:
            return None

        event_date, end_date = _parse_date_range(date_el.get_text(strip=True))
        if not event_date:
            return None  # unparseable date, skip

        link_el = card.select_one("a.clickable[href]")
        href = link_el["href"] if link_el else self.base_url

        img_el = card.select_one("img.card-img-top")
        image_url = img_el.get("src") if img_el else None

        desc_el = card.select_one("p.card-text")
        description = desc_el.get_text(strip=True) if desc_el else None

        badges = card.select(".card-tags .badge")
        category = ", ".join(b.get_text(strip=True) for b in badges) if badges else None

        return {
            "title": title,
            "event_date": event_date,
            "end_date": end_date,
            "source_url": href,
            "image_url": image_url,
            "description": description,
            "category": category,
        }
