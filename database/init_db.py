"""Database initialization script."""

import asyncio
import asyncpg
import os
from pathlib import Path
from packages.common.config import get_settings


async def init_database():
    """Initialize the database with required tables."""
    settings = get_settings()
    
    print(f"Connecting to PostgreSQL at {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    
    try:
        # Create connection pool
        pool = await asyncpg.create_pool(
            settings.postgres_dsn,
            min_size=1,
            max_size=5,
        )
        
        print("Connected to PostgreSQL")
        
        # Read the initialization SQL file
        sql_file = Path(__file__).parent / "init.sql"
        if not sql_file.exists():
            print(f"SQL file not found: {sql_file}")
            return
            
        with open(sql_file, "r", encoding="utf-8") as f:
            sql_script = f.read()
        
        # Execute the initialization script
        async with pool.acquire() as conn:
            await conn.execute(sql_script)
            
        print("Database initialized successfully!")
        print("Created table: legal_documents")
        print("Created indexes: idx_legal_documents_doc_type, idx_legal_documents_created_at, idx_legal_documents_metadata")
        print("Created table: document_relationships")
        print("Created indexes: idx_rel_source, idx_rel_target, idx_rel_type")
        
        # Close the pool
        await pool.close()
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(init_database())
