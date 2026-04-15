"""Add sample legal documents to the database for testing."""

import asyncio
import asyncpg
import uuid
import json
from packages.common.config import get_settings


async def add_sample_documents():
    """Add sample legal documents for testing."""
    settings = get_settings()
    
    print(f"Connecting to PostgreSQL at {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    
    try:
        pool = await asyncpg.create_pool(
            settings.postgres_dsn,
            min_size=1,
            max_size=5,
        )
        
        print("Connected to PostgreSQL")
        
        # Sample legal documents
        sample_docs = [
            {
                "id": str(uuid.uuid4()),
                "title": "Bộ luật Dân sự 2015",
                "content": "Bộ luật Dân sự số 91/2015/QH13 được Quốc hội thông qua ngày 24 tháng 11 năm 2015, có hiệu lực thi hành từ ngày 01 tháng 01 năm 2017. Bộ luật quy định về địa vị pháp lý, các nguyên tắc cơ bản của pháp luật dân sự, chủ thể, quyền sở hữu, nghĩa vụ và hợp đồng trong quan hệ dân sự.",
                "doc_type": "civil_code",
                "metadata": {"year": 2015, "authority": "Quốc hội", "effective_date": "2017-01-01"}
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Luật Doanh nghiệp 2020",
                "content": "Luật Doanh nghiệp số 59/2020/QH14 được Quốc hội thông qua ngày 17 tháng 6 năm 2020, có hiệu lực thi hành từ ngày 01 tháng 01 năm 2021. Luật quy định về việc thành lập, tổ chức quản lý, hoạt động và giải thể doanh nghiệp.",
                "doc_type": "enterprise_law",
                "metadata": {"year": 2020, "authority": "Quốc hội", "effective_date": "2021-01-01"}
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Bộ luật Lao động 2019",
                "content": "Bộ luật Lao động số 45/2019/QH14 được Quốc hội thông qua ngày 20 tháng 11 năm 2019, có hiệu lực thi hành từ ngày 01 tháng 01 năm 2021. Bộ luật quy định về tiêu chuẩn lao động, quyền và nghĩa vụ của người lao động và người sử dụng lao động.",
                "doc_type": "labor_code",
                "metadata": {"year": 2019, "authority": "Quốc hội", "effective_date": "2021-01-01"}
            },
        ]
        
        async with pool.acquire() as conn:
            # Insert sample documents
            for doc in sample_docs:
                await conn.execute(
                    """
                    INSERT INTO legal_documents (id, title, content, doc_type, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    doc["id"],
                    doc["title"],
                    doc["content"],
                    doc["doc_type"],
                    json.dumps(doc["metadata"])
                )
                print(f"Added document: {doc['title']}")
        
        # Count total documents
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM legal_documents")
            print(f"\nTotal documents in database: {count}")
        
        await pool.close()
        print("\nSample documents added successfully!")
        
    except Exception as e:
        print(f"Error adding sample documents: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(add_sample_documents())
