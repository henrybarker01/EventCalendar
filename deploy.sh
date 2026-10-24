#!/usr/bin/env bash
# deploy.sh — pull the latest commit and redeploy the Docker stack.
# Run this ON the Lightsail instance, from inside the repo directory.
#
#   ./deploy.sh

set -euo pipefail
cd "$(dirname "$0")"

echo "==> Pulling latest changes..."
git pull

# Create the bind-mount dir as the current user, otherwise Docker creates it root-owned
# and scp/cp of events.db into it fails with permission denied.
mkdir -p data

echo "==> Building and (re)starting containers..."
docker compose up -d --build

echo "==> Pruning old images..."
docker image prune -f

echo "==> Current status:"
docker compose ps
