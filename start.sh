#!/bin/sh

# Ensure persistent data directory exists
mkdir -p /app/data

# Map Cloudron PostgreSQL addon to our env var
if [ -n "$CLOUDRON_POSTGRESQL_URL" ]; then
    # Convert postgres:// to postgresql+asyncpg://
    ASYNC_URL=$(echo "$CLOUDRON_POSTGRESQL_URL" | sed 's|^postgres://|postgresql+asyncpg://|')
    export NORA_DATABASE_URL="$ASYNC_URL"
fi

# Set secret key from Cloudron env or generate one
if [ -z "$NORA_SECRET_KEY" ]; then
    if [ ! -f /app/data/secret_key ]; then
        python3 -c "import secrets; print(secrets.token_hex(32))" > /app/data/secret_key
    fi
    export NORA_SECRET_KEY=$(cat /app/data/secret_key)
fi

# Auto-seed on first run
if [ ! -f /app/data/.seeded ]; then
    echo "First run: seeding database..."
    python3 seed.py && touch /app/data/.seeded
fi

# Start the FastAPI application
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
