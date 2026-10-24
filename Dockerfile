# Multi-stage build: compile the Vue SPA, then package it with the FastAPI backend.
# Build context is the repo root (needs both EventScraper/ and EventView.UI/).

FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY EventView.UI/package.json EventView.UI/package-lock.json ./
RUN npm ci
COPY EventView.UI/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app/EventScraper

COPY EventScraper/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY EventScraper/ ./
COPY --from=frontend-build /build/dist /app/EventView.UI/dist

# Overridden by docker-compose to point at a mounted volume.
ENV EVENTVIEW_DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 8000

# Single worker only: the in-process reminder scheduler (APScheduler) would
# fire duplicate push notifications if multiple uvicorn workers ran it.
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
