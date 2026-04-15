"""Backfill Neo4j graph from documents already stored in PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio

from packages.common.config import get_settings
from packages.graph.sync import GraphSyncService


async def _run(limit: int | None) -> None:
    settings = get_settings()
    service = GraphSyncService(settings)
    try:
        stats = await service.sync_existing_documents(limit=limit)
        print(stats)
    finally:
        await service.close()
        await service.graph_client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync PostgreSQL legal documents into Neo4j.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of documents to sync.")
    args = parser.parse_args()
    asyncio.run(_run(args.limit))


if __name__ == "__main__":
    main()
