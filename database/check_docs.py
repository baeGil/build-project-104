"""Quick check of documents in database."""

import asyncio
import asyncpg
from packages.common.config import get_settings


async def check():
    settings = get_settings()
    pool = await asyncpg.create_pool(settings.postgres_dsn)
    
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT id, title, doc_type FROM legal_documents')
        print('Documents in database:')
        for r in rows:
            print(f'  - {r["title"]} ({r["doc_type"]})')
    
    await pool.close()


if __name__ == "__main__":
    asyncio.run(check())
