#!/usr/bin/env bash
set -e

echo "[entrypoint] Running Atlas migrations..."
cd /app/atlas

# Use "production" env if DATABASE_URL is set, otherwise "docker"
if [ -n "$DATABASE_URL" ]; then
    ATLAS_ENV="production"
else
    ATLAS_ENV="docker"
fi

atlas migrate apply --env "$ATLAS_ENV"
echo "[entrypoint] Migrations complete."

cd /app
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
