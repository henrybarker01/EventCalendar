"""
Scraper for veluwe.nl/agenda/

Card structure (as of June 2026):
    <div class="event-card block-link ...">
      <figure class="event-card__image">
        <a href="/evenement/.../"><img src="https://app.thefeedfactory.nl/..."></a>
      </figure>
      <div class="event-card__content">
        <div class="event-card__tear">
          <time class="event-card__date">
            <span class="weekday">di</span>
            <span class="day">16</span>
            <span class="month">jun</span>
          </time>
        </div>
        <div class="event-card__details">
          <p class="event-card__line">Location, City</p>
          <h3 class="event-card__title">Title</h3>
          <p class="event-card__price">Tickets vanaf €6,-</p>
          <ul class="event-card__tags categories">
            <li class="categories__item"><a class="category" href="...">Tag</a></li>
          </ul>
        </div>
      </div>
      <a class="block-link__anchor" href="/evenement/.../">Title</a>
    </div>

Dates show day + month only (no year). Year is inferred: current year unless
that date is more than 60 days in the past, in which case next year is used.
"""

from datetime import date

from base_scraper import BaseScraper

NL_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


def _parse_card_date(time_el) -> date | None:
    day_el = time_el.select_one(".day")
    month_el = time_el.select_one(".month")
    if not day_el or not month_el:
        return None
    try:
        day = int(day_el.get_text(strip=True))
        month = NL_MONTHS.get(month_el.get_text(strip=True).lower())
        if not month:
            return None
        today = date.today()
        d = date(today.year, month, day)
        if (today - d).days > 60:
            d = date(today.year + 1, month, day)
        return d
    except (ValueError, TypeError):
        return None


class VeluweNlScraper(BaseScraper):
    source_name = "veluwe"
    base_url = "https://veluwe.nl/agenda/"

    def parse_events(self) -> list[dict]:
        soup = self.fetch_page(self.base_url)
        cards = soup.select("div.event-card")
        self.logger.info("Found %d cards.", len(cards))

        events = []
        for card in cards:
            ev = self._parse_card(card)
            if ev:
                events.append(ev)
        self.logger.info("Parsed %d events.", len(events))
        return events

    def _parse_card(self, card) -> dict | None:
        title_el = card.select_one("h3.event-card__title")
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None

        link_el = card.select_one("a.block-link__anchor[href]")
        href = link_el["href"] if link_el else self.base_url

        img_el = card.select_one("figure.event-card__image img[src]")
        image_url = img_el["src"] if img_el else None

        loc_el = card.select_one("p.event-card__line")
        location = " ".join(loc_el.get_text().split()) if loc_el else None

        price_el = card.select_one("p.event-card__price")
        price = price_el.get_text(strip=True) if price_el else None

        category_els = card.select("ul.event-card__tags a.category")
        category = ", ".join(a.get_text(strip=True) for a in category_els) or None

        time_el = card.select_one("time.event-card__date")
        if not time_el:
            return None

        event_date = _parse_card_date(time_el)
        if not event_date:
            return None

        return {
            "event_type": "event",
            "title": title,
            "event_date": event_date,
            "source_url": href,
            "image_url": image_url,
            "location": location,
            "price": price,
            "category": category,
        }
