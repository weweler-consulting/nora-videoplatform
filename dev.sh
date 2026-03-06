#!/bin/bash
# Start dev environment: DB + API with hot reload
docker compose up -d db
echo "Waiting for PostgreSQL..."
sleep 2
NORA_DATABASE_URL="postgresql+asyncpg://nora:nora@localhost:5432/nora_videoplatform" \
NORA_SECRET_KEY="dev-secret" \
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
