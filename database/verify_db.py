"""Verify database setup."""

import asyncio
import asyncpg
from packages.common.config import get_settings


async def verify():
    settings = get_settings()
    pool = await asyncpg.create_pool(settings.postgres_dsn)
    
    async with pool.acquire() as conn:
        # Check if table exists
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_name = $1",
            'legal_documents'
        )
        print('Tables found:', [r['table_name'] for r in rows])
        
        # Check table structure
        if rows:
            columns = await conn.fetch(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = $1 ORDER BY ordinal_position",
                'legal_documents'
            )
            print('\nTable structure:')
            for col in columns:
                print(f"  {col['column_name']}: {col['data_type']}")
    
    await pool.close()


if __name__ == "__main__":
    asyncio.run(verify())
