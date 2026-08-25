"""Command-line entrypoint for PostgreSQL schema migrations."""

from __future__ import annotations

import asyncio
import os

from abundance_research.migrations import migrate


async def _main() -> None:
    database_url = os.environ.get("ABUNDANCE_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("ABUNDANCE_DATABASE_URL is required")
    applied = await migrate(database_url)
    print(f"Applied {len(applied)} Abundance migration(s).")


if __name__ == "__main__":
    asyncio.run(_main())

