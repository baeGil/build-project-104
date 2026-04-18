"""Helper to check which documents are already indexed."""
from qdrant_client import QdrantClient


def get_existing_document_ids(qdrant_host: str, qdrant_port: int, collection_name: str) -> set[str]:
    """Get set of already-indexed document IDs from Qdrant.
    
    This prevents re-indexing documents that already exist.
    Only new documents will be indexed on subsequent runs.
    
    Args:
        qdrant_host: Qdrant host
        qdrant_port: Qdrant port
        collection_name: Collection name
        
    Returns:
        Set of document IDs that are already indexed
    """
    try:
        client = QdrantClient(host=qdrant_host, port=qdrant_port)
        
        # Get all points from collection
        existing_ids = set()
        offset = None
        
        while True:
            records, offset = client.scroll(
                collection_name=collection_name,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            
            if not records:
                break
                
            for record in records:
                # Extract parent doc ID from point ID
                point_id = record.id
                if isinstance(point_id, str) and "_article_" in point_id:
                    # This is an article chunk, extract parent doc ID
                    parent_id = point_id.split("_article_")[0]
                    existing_ids.add(parent_id)
                else:
                    # This is a root document
                    existing_ids.add(str(point_id))
            
            if offset is None:
                break
        
        client.close()
        return existing_ids
        
    except Exception as e:
        print(f"⚠️  Could not check existing documents: {e}")
        print("→ Will index all documents (first run or connection issue)")
        return set()
