"""
Scraper for barneveldsekrant.nl/agenda — the local paper's community agenda
(Pubble platform, BDUmedia). Covers all Barneveld villages.

BDUmedia's robots.txt says scraping isn't permitted. This source is scraped for
personal use only, so keep the footprint small: listing pages only (never the
detail pages), and only as far ahead as WINDOW_DAYS (~10 requests per run).

Row structure (as of October 2026):
    <div class="component__calendar-row">
      <h5>Vandaag</h5>
      <a href="/agenda/2026/10/24/schuurverkoop-1319158">
        <span class="font-bold block">Schuurverkoop</span>
        <p class="font-light text-sm">zaterdag 24 oktober 2026 9:00 <span>tot 12:00</span></p>
        <span class="font-light text-sm">Venue | Town</span>
        <img src="https://storage.pubble.nl/..._thumb728.jpg">
      </a>
      ...
    </div>

The href carries the date (month/day NOT zero-padded) and a numeric id.
Multi-day items end with "tot zaterdag 31 oktober 18:00" (no year). There is
no description on the listing, so the time range goes in `description`.

Recurring activities reuse the same id on every date. Most are weekly routines
(taalcafé, sjoelen, inloopochtend, ...) that would bury the real events, so an
id that repeats too often inside the window is skipped — see _is_routine().
Organisers also post the same thing twice under different ids, so rows are
deduplicated on (title, date).

Pagination: ?page=N, 50 rows per page, chronological; stops on an empty page
or once rows pass the window.
"""

import re
from collections import defaultdict
from datetime import date, timedelta

from base_scraper import BaseScraper

SITE = "https://www.barneveldsekrant.nl"
WINDOW_DAYS = 120
MAX_PAGES = 20

# Not events: advice/consultation hours, garden-waste collection.
SKIP_TITLE_WORDS = ("spreekuur", "snoeiafval")

NL_MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}

HREF_RE = re.compile(r"^/agenda/(\d{4})/(\d{1,2})/(\d{1,2})/.*-(\d+)$")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
END_DAY_RE = re.compile(r"\btot\s+[a-z]+\s+(\d{1,2})\s+([a-z]+)", re.IGNORECASE)


def _is_routine(dates: list[date]) -> bool:
    """True for activities that come back every week or two.

    More than five dates in the window is never a one-off. Fewer dates count
    as routine when they're 5–14 days apart (the tail end of a weekly series,
    or a fortnightly one); dates a few days apart are more likely a multi-day
    event, and monthly ones (e.g. Repair Café) are kept.
    """
    if len(dates) > 5:
        return True
    if len(dates) < 2:
        return False
    gaps = sorted((b - a).days for a, b in zip(dates, dates[1:]))
    return 5 <= gaps[len(gaps) // 2] <= 14


def _norm_title(title: str) -> str:
    return re.sub(r"\W+", " ", title.lower()).strip()


class BarneveldseKrantScraper(BaseScraper):
    source_name = "barneveldsekrant"
    base_url = f"{SITE}/agenda"

    def parse_events(self) -> list[dict]:
        today = date.today()
        horizon = today + timedelta(days=WINDOW_DAYS)

        rows = []
        self.covered_until = horizon
        for page in range(1, MAX_PAGES + 1):
            soup = self.fetch_page(f"{self.base_url}?page={page}")
            links = soup.select('div.component__calendar-row a[href^="/agenda/"]')
            self.logger.info("Page %d: %d rows.", page, len(links))
            if not links:
                break

            page_rows = [r for r in (self._parse_row(a) for a in links) if r]
            rows.extend(r for r in page_rows if today <= r["event_date"] <= horizon)
            if page_rows and page_rows[-1]["event_date"] > horizon:
                break
        else:
            # Out of pages before the horizon: the last day seen may continue
            # on the next page, so only the days before it were seen in full.
            if rows:
                self.covered_until = rows[-1]["event_date"] - timedelta(days=1)

        dates_by_id: dict[str, list[date]] = defaultdict(list)
        for r in rows:
            dates_by_id[r["item_id"]].append(r["event_date"])
        routine_ids = {i for i, ds in dates_by_id.items() if _is_routine(sorted(set(ds)))}

        events = []
        seen: set[tuple[str, date]] = set()
        for r in rows:
            if r.pop("item_id") in routine_ids:
                continue
            if any(word in r["title"].lower() for word in SKIP_TITLE_WORDS):
                continue
            key = (_norm_title(r["title"]), r["event_date"])
            if key in seen:
                continue
            seen.add(key)
            events.append(r)

        self.logger.info(
            "%d rows in window, %d routine series skipped, %d events kept.",
            len(rows), len(routine_ids), len(events),
        )
        return events

    def _parse_row(self, a) -> dict | None:
        m = HREF_RE.match(a.get("href", ""))
        if not m:
            return None
        year, month, day, item_id = m.groups()
        try:
            event_date = date(int(year), int(month), int(day))
        except ValueError:
            return None

        title_el = a.select_one("span.font-bold")
        title = " ".join(title_el.get_text(" ", strip=True).split()) if title_el else None
        if not title:
            return None

        when_el = a.select_one("p.font-light")
        when = " ".join(when_el.get_text(" ", strip=True).split()) if when_el else ""
        times = list(dict.fromkeys(TIME_RE.findall(when)))  # "10:15 tot 10:15" → one time
        description = " – ".join(times[:2]) or None

        end_date = None
        end_m = END_DAY_RE.search(when)
        if end_m and end_m.group(2).lower() in NL_MONTHS:
            end_date = date(event_date.year, NL_MONTHS[end_m.group(2).lower()], int(end_m.group(1)))
            if end_date < event_date:
                end_date = date(event_date.year + 1, end_date.month, end_date.day)

        # "Venue | Town"; either part may be empty or the placeholder "Onbekend"
        loc_el = a.select_one("span.font-light")
        parts = []
        if loc_el:
            for part in loc_el.get_text(" ", strip=True).split("|"):
                part = " ".join(part.split())
                if part and part.lower() != "onbekend" and part not in parts:
                    parts.append(part)
        location = ", ".join(parts) or None

        img_el = a.select_one("img[src]")

        return {
            "item_id": item_id,
            "event_type": "event",
            "title": title,
            "event_date": event_date,
            "end_date": end_date,
            "source_url": SITE + a["href"],
            "image_url": img_el["src"] if img_el else None,
            "location": location,
            "description": description,
        }
