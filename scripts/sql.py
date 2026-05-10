"""Run a SQL statement against the production database from inside the container.

Usage (inside the kurse Cloudron container):
    python3 scripts/sql.py "DELETE FROM stripe_processed_events WHERE event_id = 'evt_xxx'"
    python3 scripts/sql.py "SELECT email, name FROM users WHERE email LIKE '%test%'"

Bypasses the FastAPI app config layer (no NORA_SECRET_KEY etc. required) by
connecting via asyncpg directly to CLOUDRON_POSTGRESQL_URL.

For SELECT queries: prints each row as a dict, plus row count.
For DML: prints asyncpg's status string (e.g. "DELETE 1").
"""
import asyncio
import os
import sys

import asyncpg


async def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python3 scripts/sql.py "<SQL>"', file=sys.stderr)
        sys.exit(1)
    sql = sys.argv[1]

    url = os.environ.get("CLOUDRON_POSTGRESQL_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("CLOUDRON_POSTGRESQL_URL not set in environment", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(url)
    try:
        if sql.lstrip().lower().startswith(("select", "show", "explain", "with")):
            rows = await conn.fetch(sql)
            for row in rows:
                print(dict(row))
            print(f"({len(rows)} rows)")
        else:
            result = await conn.execute(sql)
            print(result)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
