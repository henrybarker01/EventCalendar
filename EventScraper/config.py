import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Overridable so Docker can point this at a mounted volume (e.g. /data)
# that survives container rebuilds; defaults to the old Pi behaviour.
DATA_DIR = os.environ.get("EVENTVIEW_DATA_DIR", BASE_DIR)

DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'events.db')}"

REQUEST_TIMEOUT = 15  # seconds
REQUEST_DELAY = 1.0   # seconds between requests
MAX_WORKERS = 2       # tuned for Raspberry Pi 4B

# Sources that cover a wider region (veluwe, wattedoenin) keep only events
# within this distance of Barneveld centre.
HOME_LAT, HOME_LNG = 52.1403, 5.5832
MAX_DISTANCE_KM = 25

# After each scrape run, events that ended longer ago than this are deleted
# (starred ones are kept), along with scraping logs of the same age.
KEEP_PAST_DAYS = 90

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; EventViewBot/1.0; "
        "+https://github.com/henrybarker01/EventCalendar)"
    )
}
