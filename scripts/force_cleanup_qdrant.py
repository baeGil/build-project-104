#!/usr/bin/env python3
"""Force cleanup Qdrant - delete ALL points with UUID-style IDs."""

from qdrant_client import QdrantClient
from packages.common.config import get_settings

def cleanup_qdrant():
    settings = get_settings()
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    
    print("=" * 70)
    print("🧹 QDRANT FORCE CLEANUP")
    print("=" * 70)
    
    # Get collection info
    info = client.get_collection(settings.qdrant_collection)
    total_before = info.points_count
    print(f"\nTotal points before: {total_before:,}")
    
    # Scroll all points and identify test docs
    print("\n🔍 Scanning for test/sample points...")
    
    records, _ = client.scroll(
        collection_name=settings.qdrant_collection,
        limit=min(total_before, 10000),
        with_payload=True,
        with_vectors=False,
    )
    
    test_point_ids = []
    real_point_ids = []
    
    for record in records:
        payload = record.payload or {}
        law_id = payload.get('law_id', '')
        title = payload.get('title', '')
        
        # UUID pattern: contains multiple dashes and is long
        is_uuid = ('-' in law_id and len(law_id) > 30) or \
                  title in ['Test Document', 'Document 1', 'Law 1', 'Law 2', 'Doc 2'] or \
                  law_id.startswith('test') or \
                  law_id.startswith('doc-')
        
        if is_uuid:
            test_point_ids.append(record.id)
        else:
            real_point_ids.append(record.id)
    
    print(f"  Real documents (numeric/alphanumeric law_id): {len(real_point_ids)}")
    print(f"  Test documents (UUID-style): {len(test_point_ids)}")
    
    if not test_point_ids:
        print("\n✅ No test points found!")
        client.close()
        return
    
    # Delete test points
    print(f"\n🗑️  Deleting {len(test_point_ids)} test points...")
    
    batch_size = 100
    deleted = 0
    
    for i in range(0, len(test_point_ids), batch_size):
        batch = test_point_ids[i:i+batch_size]
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=batch,
        )
        deleted += len(batch)
        if deleted % 200 == 0:
            print(f"  Deleted {deleted:,}/{len(test_point_ids):,}...")
    
    print(f"\n✅ Deleted {deleted:,} test points")
    
    # Verify
    info_after = client.get_collection(settings.qdrant_collection)
    total_after = info_after.points_count
    print(f"\nTotal points after: {total_after:,}")
    print(f"Removed: {total_before - total_after:,} points")
    
    print("\n" + "=" * 70)
    print("✅ QDRANT CLEANUP COMPLETE")
    print("=" * 70)
    
    client.close()

if __name__ == "__main__":
    cleanup_qdrant()
