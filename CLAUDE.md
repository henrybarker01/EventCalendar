# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project structure

```
EventView/
├── EventScraper/        # Python scraping pipeline + FastAPI backend
└── EventView.UI/        # Vue 3 frontend (to be built)
```

## EventScraper — commands

Run these from inside `EventScraper/`:

```bash
# Setup
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Database
python main.py --init-db       # Initialize/reset the SQLite database

# Scraping
python main.py --scraper barneveld   # Run a single scraper by name
python main.py --all                 # Run all registered scrapers
python main.py --schedule            # Run all scrapers every 24 h (blocking)

# API server (http://localhost:8000)
python api.py

# Utilities
python view_db.py              # Interactive database viewer
python view_db.py --export     # Export events to CSV
python test_setup.py           # System verification / smoke test
```

## Architecture

```
Website HTML → base_scraper.fetch_page() → BeautifulSoup → scraper.parse_events()
  → base_scraper.save_events() → SQLite (events.db)
  → api.py (FastAPI) → EventView.UI/ (Vue 3 SPA)
```

**Scraper framework** (`EventScraper/base_scraper.py`): Abstract base class. Subclasses only implement `parse_events()` — fetching, saving, deduplication, and logging are handled by the base class. Deduplication is by `(source_url, event_date)`.

**Scraper registry** (`EventScraper/main.py`): The `SCRAPERS` dict maps CLI names to scraper classes. Register new scrapers here.

**Models** (`EventScraper/models.py`): Two SQLAlchemy tables — `Event` (13 fields including `is_active`) and `ScrapingLog` (tracks every scraping attempt with status and error messages).

**API** (`EventScraper/api.py`): FastAPI app with CORS enabled. Serves the Vue frontend static build from `EventView.UI/dist/` when present.

**Config** (`EventScraper/config.py`): Central place for `DATABASE_URL`, `REQUEST_TIMEOUT`, `REQUEST_DELAY` (1 s between requests), and `MAX_WORKERS` (2, tuned for Raspberry Pi 4B — the target deployment platform).

## Adding a New Scraper

1. Copy `EventScraper/scraper_template.py` into `EventScraper/scrapers/` and implement `parse_events()`.
2. Add an entry to the `SCRAPERS` dict in `EventScraper/main.py`.
3. Run `python main.py --scraper <name>` to test it.

The working reference implementation is [`EventScraper/scrapers/barneveld_centrum.py`](EventScraper/scrapers/barneveld_centrum.py).
