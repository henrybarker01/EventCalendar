import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'events.db')}"

REQUEST_TIMEOUT = 15  # seconds
REQUEST_DELAY = 1.0   # seconds between requests
MAX_WORKERS = 2       # tuned for Raspberry Pi 4B

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; EventViewBot/1.0; "
        "+https://github.com/henrybarker01/EventCalendar)"
    )
}
