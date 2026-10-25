# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project overview

EventView is an event aggregator for the Barneveld region. It scrapes event websites daily, stores them in SQLite, and serves them via a FastAPI + Vue 3 web app.

**Target deployment:** AWS Lightsail, as Docker containers behind the server's shared Caddy, at `https://calendar.aeromech.co`

## Project structure

```
EventView/
├── Dockerfile                  # Multi-stage: builds Vue, packages with FastAPI backend
├── docker-compose.yml          # Services: api, scraper (Caddy lives in the AeroMechUI project)
├── deploy.sh                   # Run on the server: git pull + docker compose up -d --build
├── data/                       # Bind-mounted volume: events.db, vapid_keys.json (git-ignored, server-only)
├── EventScraper/               # Python backend
│   ├── scrapers/               # One file per source website
│   │   └── barneveld_centrum.py
│   ├── api.py                  # FastAPI — REST API + serves Vue dist/
│   ├── base_scraper.py         # Abstract base class for all scrapers
│   ├── config.py               # DB path (EVENTVIEW_DATA_DIR-overridable), timeouts, worker tuning, 25 km radius
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

- **SQLite** via SQLAlchemy — zero server, single file (`events.db`). Path is `$EVENTVIEW_DATA_DIR/events.db`, defaulting to `EventScraper/` when unset; Docker sets it to `/data`, a bind-mounted host directory, so data survives container rebuilds.
- **Deduplication** by `(source_url, event_date)` — safe to run scrapers repeatedly.
- **Image proxy** at `GET /api/image-proxy?url=...` — source sites block hotlinking, so images are fetched server-side by FastAPI and streamed to the browser. Vue components always use `/api/image-proxy?url=...` instead of direct image URLs.
- **One app container, fronted by a shared Caddy** — the `api` container runs `uvicorn api:app` (single worker — see below) serving both the REST API and the built Vue SPA from `EventView.UI/dist/`. EventView has no Caddy of its own: the Lightsail box already runs `aeromechui-caddy-1` (from `~/AeroMechUI`), which owns ports 80/443 for all sites. `api` joins that project's external `aeromechui_default` network under the alias `eventview-api`, and the `calendar.aeromech.co` block lives in `/home/ubuntu/AeroMechUI/Caddyfile` (`reverse_proxy eventview-api:8000`).
- **Separate `scraper` container** runs `main.py --schedule` (the same daily loop used everywhere), sharing the SQLite file with `api` via the `./data` bind mount. This replaces the old Pi cron job.
- **Single uvicorn worker only** — the reminder scheduler (APScheduler `BackgroundScheduler`, polling every minute inside `api.py`) runs in-process. Multiple workers would each run their own scheduler and send duplicate push notifications.
- **Hash routing** in Vue (`createWebHashHistory`) so FastAPI's catch-all route serves `index.html` for all `/#/...` paths without conflicts.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/events` | List events. Query params: `source`, `from_date` (also matches events still running, i.e. `end_date >= from_date`), `to_date`, `active_only`, `limit`, `offset`. The UI always sends `from_date` (today, or the calendar's first visible day) so past rows can't fill the limit |
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

To test the Docker build itself locally, first `docker network create aeromechui_default` (the compose file expects that external network to exist), then run `docker compose up --build` from the repo root and check `docker compose logs -f api`. HTTPS/Caddy can only be exercised on the server against the real domain.

## Deploying to Lightsail

Deployment pulls from git — there is no scp/build-and-copy step anymore. Push (or merge) to `main`, then on the Lightsail instance:

```bash
cd ~/EventView   # wherever the repo was cloned
./deploy.sh      # git pull && docker compose up -d --build
```

`deploy.sh` also prunes dangling images and prints `docker compose ps` so you can confirm both services (`api`, `scraper`) are up.

**One-time server setup** (already done on the current instance, but for reference):
```bash
git clone https://github.com/henrybarker01/EventCalendar.git EventView
cd EventView
mkdir -p data                    # create it yourself so it isn't root-owned by Docker
# optional: copy an existing events.db / vapid_keys.json into data/ first
docker compose up -d --build
```

Requires on the instance: Docker + Docker Compose plugin, git, DNS for `calendar.aeromech.co` pointed at the instance's static IP, and the AeroMechUI stack running (its network must exist before `docker compose up`). Its Caddyfile needs:
```
calendar.aeromech.co {
	encode gzip
	reverse_proxy eventview-api:8000
}
```
After editing it: `cd ~/AeroMechUI && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile`. Certificates live in AeroMechUI's `caddy_data` volume.

Useful commands on the server:
```bash
docker compose logs -f api        # API logs
docker compose logs -f scraper    # Scrape run history (replaces the old scraper.log)
docker logs -f aeromechui-caddy-1 # TLS/reverse-proxy issues (shared Caddy)
docker compose exec api python view_db.py --logs
```

## Adding a new scraper

1. Copy `EventScraper/scraper_template.py` into `EventScraper/scrapers/<name>.py`.
2. Set `source_name` and `base_url` on the class.
3. Implement `parse_events()` — return a list of dicts with at minimum `title`, `event_date` (a `datetime.date`), and `source_url`.
4. Add an entry to `SCRAPERS` in `EventScraper/main.py`.
5. Test with `python main.py --scraper <name>`.

Reference implementation: [`EventScraper/scrapers/barneveld_centrum.py`](EventScraper/scrapers/barneveld_centrum.py).

If the source covers a wider region than Barneveld, keep only nearby events with `is_nearby(lat, lng)` from `base_scraper.py` (radius `MAX_DISTANCE_KM` in `config.py`) — see `veluwe_nl.py` and `wattedoenin_nl.py`.

Rows are deduplicated on `(source_url, event_date)`, so never use a date that moves from day to day (such as a "next date" that rolls forward); emit one row per real date instead.

If a new site blocks hotlinking, add its hostname to the `allowed_hosts` list in the `image_proxy` endpoint in `api.py`.
