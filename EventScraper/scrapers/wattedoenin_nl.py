"""
Scraper for wattedoenin.nl/uitagenda/gelderland/ and /uitagenda/utrecht/

Barneveld sits near the provincial border, so the Utrecht agenda is read too
(Amersfoort, Veenendaal, the Heuvelrug). Both cover a whole province; cards
are filtered here to MAX_DISTANCE_KM around Barneveld, which usually leaves
only a handful.

Card structure (div.evenement with Schema.org microdata, as of October 2026):
    <div class="evenement" itemscope itemtype="http://schema.org/Event">
      <h3><span itemprop="name">Event Title</span></h3>
      <a href="https://www.wattedoenin.nl/evenementen/slug/" itemprop="url">
        <img data-src="...-100x100.jpg"
             data-srcset="...-100x100.jpg 100w, ...original.jpg 120w, ...original.jpg 200w">
      </a>
      <div class="event-excerpt">
        <span itemprop="location" ...>
          <span itemprop="name">Venue</span>,
          <span itemprop="address" ...><span itemprop="addressLocality">City</span></span>
          <span itemprop="geo" ...>
            <meta content="52.098152" itemprop="latitude"/>
            <meta content="5.829219" itemprop="longitude"/>
          </span>
        </span>
        - <span itemprop="description">...</span>
      </div>
      <div>
        <strong>
          <meta content="2026-10-10T00:00:00+02:00" itemprop="startDate"/> ... t/m
          <meta content="2026-10-25T23:59:59+01:00" itemprop="endDate"/> ...
        </strong>
      </div>
    </div>

Pagination (WordPress Events Manager, 15 cards per page) is ?pno=N; this
follows .em-pagination a.next until there is none. (/page/N/ just serves
page 1 again.)
Dates are ISO 8601 with TZ offset — parsed with datetime.fromisoformat().
Images are lazy-loaded; actual URL is in data-srcset (largest) or data-src.
"""

from datetime import date, datetime
from urllib.parse import urljoin

from base_scraper import BaseScraper, is_nearby

SITE = "https://www.wattedoenin.nl"
REGIONS = ("gelderland", "utrecht")
MAX_PAGES = 15  # per region


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


def _geo(card) -> tuple[float, float] | None:
    lat_el = card.select_one("[itemprop='geo'] meta[itemprop='latitude']")
    lng_el = card.select_one("[itemprop='geo'] meta[itemprop='longitude']")
    try:
        return float(lat_el["content"]), float(lng_el["content"])
    except (TypeError, KeyError, ValueError):
        return None


class WattedoeninNlScraper(BaseScraper):
    source_name = "wattedoenin"
    base_url = f"{SITE}/uitagenda/"

    def parse_events(self) -> list[dict]:
        events = []
        seen_urls: set[str] = set()
        total = 0

        for region in REGIONS:
            url = f"{self.base_url}{region}/"
            for page in range(1, MAX_PAGES + 1):
                soup = self.fetch_page(url)
                cards = soup.select("div.evenement")
                self.logger.info("%s page %d: %d cards.", region, page, len(cards))
                total += len(cards)

                for card in cards:
                    geo = _geo(card)
                    if geo is None or not is_nearby(*geo):
                        continue
                    ev = self._parse_card(card)
                    if ev and ev["source_url"] not in seen_urls:
                        seen_urls.add(ev["source_url"])
                        events.append(ev)

                next_el = soup.select_one(".em-pagination a.next[href]")
                if not next_el:
                    break
                url = urljoin(url, next_el["href"])

        self.logger.info("%d cards, %d events nearby.", total, len(events))
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
