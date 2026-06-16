# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project overview

EventView is a Raspberry Pi-hosted event aggregator for the Barneveld region. It scrapes event websites daily, stores them in SQLite, and serves them via a FastAPI + Vue 3 web app accessible on the local network.

**Target deployment:** Raspberry Pi 4B at `192.168.178.240:8000`

## Project structure

```
EventView/
├── EventScraper/               # Python backend
│   ├── scrapers/               # One file per source website
│   │   └── barneveld_centrum.py
│   ├── api.py                  # FastAPI — REST API + serves Vue dist/
│   ├── base_scraper.py         # Abstract base class for all scrapers
│   ├── config.py               # DB path, timeouts, Pi-tuned settings
│   ├── main.py                 # CLI entry point + scraper registry
│   ├── models.py               # SQLAlchemy: Event + ScrapingLog tables
│   ├── scraper_template.py     # Starting point for new scrapers
│   ├── test_setup.py           # Smoke test / system check
│   ├── view_db.py              # CLI database viewer + CSV export
│   └── requirements.txt
└── EventView.UI/               # Vue 3 frontend
    ├── src/
    │   ├── api/client.ts       # Axios API client + TypeScript types
    │   ├── components/
    │   │   └── EventCard.vue   # Event card (images via proxy)
    │   ├── router/index.ts     # Vue Router (hash history)
    │   ├── stores/events.ts    # Pinia store — events, filters, search
    │   ├── views/
    │   │   ├── EventsView.vue  # Main grid view with filter bar
    │   │   └── EventDetailView.vue
    │   ├── App.vue
    │   ├── main.ts
    │   └── style.css           # Plain CSS, no framework
    ├── vite.config.ts          # Proxy /api → localhost:8000 in dev
    └── dist/                   # Production build (git-ignored)
```

## Key architectural decisions

- **SQLite** via SQLAlchemy — zero server, single file (`EventScraper/events.db`, git-ignored).
- **Deduplication** by `(source_url, event_date)` — safe to run scrapers repeatedly.
- **Image proxy** at `GET /api/image-proxy?url=...` — source sites block hotlinking, so images are fetched server-side by FastAPI and streamed to the browser. Vue components always use `/api/image-proxy?url=...` instead of direct image URLs.
- **Single process on Pi** — `python api.py` serves both the REST API and the built Vue SPA from `EventView.UI/dist/`. No Nginx needed for the app itself (Nginx is already used by Klipper/Mainsail on port 80).
- **Hash routing** in Vue (`createWebHashHistory`) so FastAPI's catch-all route serves `index.html` for all `/#/...` paths without conflicts.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/events` | List events. Query params: `source`, `from_date`, `to_date`, `active_only`, `limit`, `offset` |
| GET | `/api/events/{id}` | Single event |
| GET | `/api/sources` | List of registered source names |
| GET | `/api/logs` | Recent scraping run history |
| GET | `/api/image-proxy?url=...` | Proxy a remote image (hotlink bypass) |
| POST | `/api/scrape/{source_name}` | Manually trigger a scraper run |

## EventScraper — commands

Run from inside `EventScraper/`:

```bash
# First-time setup
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux / Pi
pip install -r requirements.txt

# Database
python main.py --init-db     # Create tables (safe to re-run)

# Scraping
python main.py --scraper barneveld   # Run one scraper by name
python main.py --all                 # Run all registered scrapers
python main.py --schedule            # Run all scrapers every 24 h (blocking)

# API server
python api.py                # Starts on http://0.0.0.0:8000

# Utilities
python view_db.py            # Browse events in the terminal
python view_db.py --logs     # Show scraping run history
python view_db.py --export   # Export events to events.csv
python test_setup.py         # Smoke test (imports, DB, network)
```

## EventView.UI — commands

Run from inside `EventView.UI/`:

```bash
npm install          # First time
npm run dev          # Dev server on :5173, proxies /api to :8000
npm run build        # Production build → dist/
```

## Development workflow (local Windows machine)

```
Terminal 1: cd EventScraper && python api.py         # API on :8000
Terminal 2: cd EventView.UI && npm run dev           # UI on :5173
```

The Vite dev server proxies all `/api` requests to `:8000`, so both servers must be running.

## Deploying to the Pi

Build the frontend locally, then copy to the Pi:

```powershell
# Build
cd EventView.UI; npm run build

# Copy to Pi (from Windows PowerShell)
scp "EventScraper\api.py" pi@192.168.178.240:/home/pi/EventView/EventScraper/api.py
scp -r "EventView.UI\dist" pi@192.168.178.240:/home/pi/EventView/EventView.UI/
```

On the Pi:
```bash
sudo systemctl restart eventview
```

The systemd service file is at `/etc/systemd/system/eventview.service`. It runs `python api.py` as user `pi` from `/home/pi/EventView/EventScraper`.

The daily scraper runs via cron (crontab for user `pi`):
```
0 6 * * * cd /home/pi/EventView/EventScraper && venv/bin/python main.py --all >> /home/pi/EventView/scraper.log 2>&1
```

## Adding a new scraper

1. Copy `EventScraper/scraper_template.py` into `EventScraper/scrapers/<name>.py`.
2. Set `source_name` and `base_url` on the class.
3. Implement `parse_events()` — return a list of dicts with at minimum `title`, `event_date` (a `datetime.date`), and `source_url`.
4. Add an entry to `SCRAPERS` in `EventScraper/main.py`.
5. Test with `python main.py --scraper <name>`.

Reference implementation: [`EventScraper/scrapers/barneveld_centrum.py`](EventScraper/scrapers/barneveld_centrum.py).

If a new site blocks hotlinking, add its hostname to the `allowed_hosts` list in the `image_proxy` endpoint in `api.py`.

## Pi environment notes

- The Pi also runs Klipper (3D printer firmware) with Moonraker on port 7125 and Mainsail/Fluidd on port 80 via Nginx. These do not conflict with EventView on port 8000.
- Python version on Pi: 3.x (Debian-based, Raspberry Pi OS).
- `venv` lives inside `EventScraper/` on the Pi, not committed to git.
- `events.db` lives inside `EventScraper/` on the Pi, not committed to git.
