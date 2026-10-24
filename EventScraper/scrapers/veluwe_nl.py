"""
Scraper for veluwe.nl/agenda/

One request returns every card for the whole Veluwe (~390). robots.txt asks
for a 10 s crawl-delay, so this makes just that one listing request and never
visits detail pages. The site ignores city[] filters, so cards are filtered
here to MAX_DISTANCE_KM around Barneveld (~250 left).

Card structure (as of October 2026):
    <div class="listing-events-grid__item">
      <div class="event-card block-link ..." data-lat="52.300965" data-lng="5.629492" ...>
        <figure class="event-card__image ...">
          <a href="..."><img src="https://app.thefeedfactory.nl/..."></a>
        </figure>
        <div class="event-card__content">
          <div class="event-card__details">
            <p class="event-card__date">za 24 okt 2026</p>
            <h3 class="event-card__title">Title</h3>
            <p class="event-card__line">Venue, Town</p>
            <div class="event-card__footer">
              <ul class="event-card__tags tags">
                <li class="tags__item"><a class="tag" href="...">Tag</a></li>
              </ul>
              <p class="event-card__price">Tickets vanaf €4,50</p>
            </div>
          </div>
        </div>
        <a class="block-link__anchor" href="https://veluwe.nl/evenement/.../">Title</a>
      </div>
      <div class="event-card-extend">                     ← multi-date events only
        <div class="event-moredates">
          <ul class="event-moredates__list">
            <li class="event-moredates__item">
              <span class="event-moredates__date">za 24 okt 2026</span> ...
            </li>
            ...                                           ← at most 4, then "Bekijk alle data"
          </ul>
        </div>
      </div>
    </div>

The card date is the event's *next* date, so on a multi-date event it moves
every day. Rows are deduplicated on (source_url, event_date), so each
event-moredates__date becomes its own row instead. Only the next four dates
are listed, so a long-running event gains a row whenever a new date comes
into view. Open-ended events (mostly exhibitions) have no date list and just
show their next open day, so they likewise get a row per open day.

About 20 cards have no data-lat/data-lng. For those, the town after the last
comma in event-card__line is looked up in the page's cityArrayData script
(the coordinates behind the site's own town filter); cards that still can't
be placed are skipped.
"""

import json
import re
from datetime import date
from urllib.parse import urljoin

from base_scraper import BaseScraper, is_nearby

NL_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "maa": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}

DATE_RE = re.compile(r"(\d{1,2})\s+([a-z]{3})[a-z]*\.?\s+(\d{4})", re.IGNORECASE)
CITY_DATA_RE = re.compile(r"var cityArrayData\s*=\s*(\{.*?\});", re.DOTALL)


def _text(el) -> str:
    return " ".join(el.get_text().split()) if el else ""


def _parse_date(text: str) -> date | None:
    """'za 24 okt 2026' → date(2026, 10, 24)."""
    m = DATE_RE.search(text)
    month = NL_MONTHS.get(m.group(2).lower()) if m else None
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def _location(card) -> str:
    """'Venue, Town', minus the stray spaces and trailing commas some cards have."""
    return _text(card.select_one("p.event-card__line")).replace(" ,", ",").strip(" ,")


def _town_coords(soup) -> dict[str, tuple[float, float]]:
    """Town slug (e.g. 't-harde') → (lat, lng), from the cityArrayData script."""
    script = soup.find("script", string=CITY_DATA_RE)
    if not script:
        return {}
    try:
        data = json.loads(CITY_DATA_RE.search(script.string).group(1))
        return {slug: (float(c["lat"]), float(c["lng"])) for slug, c in data.items()}
    except (ValueError, KeyError, TypeError):
        return {}


class VeluweNlScraper(BaseScraper):
    source_name = "veluwe"
    base_url = "https://veluwe.nl/agenda/"

    def parse_events(self) -> list[dict]:
        soup = self.fetch_page(self.base_url)
        towns = _town_coords(soup)
        if not towns:
            self.logger.warning("No cityArrayData on the page; cards without coordinates are skipped.")
        cards = soup.select("div.event-card")

        events = []
        seen: set[tuple[str, date]] = set()
        nearby = unplaced = 0
        for card in cards:
            coords = self._coords(card, towns)
            if coords is None:
                unplaced += 1
                continue
            if not is_nearby(*coords):
                continue
            nearby += 1
            for ev in self._parse_card(card):
                key = (ev["source_url"], ev["event_date"])
                if key not in seen:
                    seen.add(key)
                    events.append(ev)

        self.logger.info(
            "%d cards: %d nearby, %d without a location; %d rows (one per listed date).",
            len(cards), nearby, unplaced, len(events),
        )
        return events

    def _coords(self, card, towns: dict[str, tuple[float, float]]) -> tuple[float, float] | None:
        try:
            return float(card["data-lat"]), float(card["data-lng"])
        except (KeyError, ValueError):
            pass
        town = _location(card).rsplit(",", 1)[-1].strip()
        return towns.get(re.sub(r"[^a-z0-9]+", "-", town.lower()).strip("-"))

    def _parse_card(self, card) -> list[dict]:
        title = _text(card.select_one("h3.event-card__title"))
        link_el = card.select_one("a.block-link__anchor[href]")
        if not title or not link_el:
            return []

        # Multi-date events list their upcoming dates in the sibling block;
        # the card's own date is the first of them.
        date_els = card.select("p.event-card__date")
        more = card.find_next_sibling()
        if more is not None and "event-card-extend" in more.get("class", []):
            date_els = more.select("span.event-moredates__date") or date_els
        dates = sorted({d for d in (_parse_date(_text(el)) for el in date_els) if d})

        img_el = card.select_one("figure.event-card__image img[src]")
        tag_els = card.select("ul.event-card__tags a.tag")

        return [
            {
                "event_type": "event",
                "title": title,
                "event_date": event_date,
                "source_url": urljoin(self.base_url, link_el["href"]),
                "image_url": img_el["src"] if img_el else None,
                "location": _location(card) or None,
                "price": _text(card.select_one("p.event-card__price")) or None,
                "category": ", ".join(_text(a) for a in tag_els) or None,
            }
            for event_date in dates
        ]
