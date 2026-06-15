"""
Scraper for visitregiobarneveld.nl/agenda/

Card structure (as of June 2026):
    <div class="card position-relative">
      <div class="card-img-wrapper"><img class="card-img-top ..."></div>
      <div class="card-tags"><span class="badge">Category</span></div>
      <div class="card-content">
        <h3 class="h5">Title</h3>
        <p class="card-text">Short description</p>
        <p class="card-date">Za 20 jun 2026</p>
      </div>
      <a class="clickable" href="...full event URL..."></a>
    </div>
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


def _parse_dutch_date(text: str) -> date | None:
    if not text:
        return None
    text = NL_DAY_PREFIX.sub("", text.strip())
    for nl, num in NL_MONTHS.items():
        text = re.sub(rf"\b{nl}\b", str(num), text, flags=re.IGNORECASE)
    try:
        return dateparser.parse(text, dayfirst=True).date()
    except Exception:
        return None


class BarneveldCentrumScraper(BaseScraper):
    source_name = "barneveld"
    base_url = "https://visitregiobarneveld.nl/agenda/"

    def parse_events(self) -> list[dict]:
        soup = self.fetch_page(self.base_url)
        cards = soup.select("div.card.position-relative")
        self.logger.info("Found %d cards.", len(cards))

        events = []
        for card in cards:
            event = self._parse_card(card)
            if event:
                events.append(event)
        return events

    def _parse_card(self, card) -> dict | None:
        title_el = card.select_one("h3, h2")
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None

        link_el = card.select_one("a.clickable[href]")
        href = link_el["href"] if link_el else self.base_url

        date_el = card.select_one("p.card-date")
        raw_date = date_el.get_text(strip=True) if date_el else ""
        event_date = _parse_dutch_date(raw_date) or date.today()

        img_el = card.select_one("img.card-img-top")
        image_url = img_el.get("src") if img_el else None

        desc_el = card.select_one("p.card-text")
        description = desc_el.get_text(strip=True) if desc_el else None

        badges = card.select(".card-tags .badge")
        category = ", ".join(b.get_text(strip=True) for b in badges) if badges else None

        return {
            "title": title,
            "event_date": event_date,
            "source_url": href,
            "image_url": image_url,
            "description": description,
            "category": category,
        }
