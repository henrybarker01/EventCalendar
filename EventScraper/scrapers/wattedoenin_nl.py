"""
Scraper for wattedoenin.nl/uitagenda/gelderland/

Card structure (div.evenement with Schema.org microdata):
    <div class="evenement" itemscope itemtype="http://schema.org/Event">
      <h3><span itemprop="name">Event Title</span></h3>
      <a href="/evenementen/slug/" itemprop="url">
        <img data-src="...-100x100.jpg"
             data-srcset="...-100x100.jpg 100w, ...original.jpg 120w, ...original.jpg 200w">
      </a>
      <div class="event-excerpt">
        <span itemprop="location" ...>
          <span itemprop="name">Venue</span>,
          <span itemprop="addressLocality">City</span>
        </span>
        - <span itemprop="description">...</span>
      </div>
      <div>
        <meta content="2026-06-13T00:00:00+02:00" itemprop="startDate"/>
        <meta content="2026-06-21T23:59:59+02:00" itemprop="endDate"/>
      </div>
    </div>

Pagination: WordPress /page/N/ style; stops when a page returns 0 cards.
Dates are ISO 8601 with TZ offset — parsed with datetime.fromisoformat().
Images are lazy-loaded; actual URL is in data-srcset (largest) or data-src.
"""

from datetime import date, datetime, timezone

from base_scraper import BaseScraper

BASE_URL = "https://www.wattedoenin.nl/uitagenda/gelderland/"
MAX_PAGES = 15


def _largest_from_srcset(srcset: str) -> str | None:
    parts = [p.strip() for p in srcset.split(",") if p.strip()]
    if not parts:
        return None
    return parts[-1].split()[0]


def _parse_iso_date(content: str) -> date | None:
    try:
        return datetime.fromisoformat(content).date()
    except (ValueError, TypeError):
        return None


class WattedoeninNlScraper(BaseScraper):
    source_name = "wattedoenin"
    base_url = BASE_URL

    def parse_events(self) -> list[dict]:
        events = []
        seen_urls: set[str] = set()

        for page in range(1, MAX_PAGES + 1):
            url = BASE_URL if page == 1 else f"{BASE_URL}page/{page}/"
            soup = self.fetch_page(url)
            cards = soup.select("div.evenement")
            self.logger.info("Page %d: %d cards.", page, len(cards))

            if not cards:
                break

            new_on_page = 0
            for card in cards:
                ev = self._parse_card(card)
                if ev and ev["source_url"] not in seen_urls:
                    seen_urls.add(ev["source_url"])
                    events.append(ev)
                    new_on_page += 1

            # If every card on this page was already seen, we've looped back
            if new_on_page == 0:
                break

        self.logger.info("Total unique events: %d.", len(events))
        return events

    def _parse_card(self, card) -> dict | None:
        title_el = card.select_one("span[itemprop='name']")
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None

        link_el = card.select_one("a[itemprop='url'][href]")
        href = link_el["href"] if link_el else self.base_url

        img_el = card.select_one("a[itemprop='url'] img")
        image_url = None
        if img_el:
            srcset = img_el.get("data-srcset", "")
            image_url = _largest_from_srcset(srcset) or img_el.get("data-src")

        start_el = card.select_one("meta[itemprop='startDate']")
        end_el = card.select_one("meta[itemprop='endDate']")
        event_date = _parse_iso_date(start_el["content"]) if start_el else None
        end_date = _parse_iso_date(end_el["content"]) if end_el else None
        if not event_date:
            return None

        loc_name_el = card.select_one("span[itemprop='location'] span[itemprop='name']")
        loc_city_el = card.select_one("span[itemprop='location'] span[itemprop='addressLocality']")
        loc_name = loc_name_el.get_text(strip=True) if loc_name_el else ""
        loc_city = loc_city_el.get_text(strip=True) if loc_city_el else ""
        if loc_name and loc_city and loc_name != loc_city:
            location = f"{loc_name}, {loc_city}"
        else:
            location = loc_name or loc_city or None

        return {
            "event_type": "event",
            "title": title,
            "event_date": event_date,
            "end_date": end_date,
            "source_url": href,
            "image_url": image_url,
            "location": location,
        }
