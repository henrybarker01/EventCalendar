"""
Template for new scrapers. Copy into scrapers/<name>.py and implement parse_events().
Then register it in the SCRAPERS dict in main.py.
"""

from base_scraper import BaseScraper


class MyScraper(BaseScraper):
    source_name = "my_source"   # unique slug, used as CLI name
    base_url = "https://example.com/events/"

    def parse_events(self) -> list[dict]:
        soup = self.fetch_page(self.base_url)
        events = []

        for card in soup.select(".event-card"):  # adjust selector
            title = card.select_one("h2, h3").get_text(strip=True)
            link = card.select_one("a")["href"]
            # ... parse date, image, location etc.

            events.append({
                "title": title,
                "event_date": ...,   # datetime.date object
                "source_url": link,
                # optional: end_date, location, description, image_url, category, price
            })

        return events
