"""Check actual document counts in Qdrant and OpenSearch."""
import asyncio
from rich.console import Console
from packages.common.config import get_settings
from opensearchpy import OpenSearch

console = Console()

async def check_qdrant():
    """Check Qdrant collection stats."""
    try:
        from qdrant_client import QdrantClient
        settings = get_settings()
        
        client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        
        collection_name = settings.qdrant_collection
        
        # Get collection info
        info = client.get_collection(collection_name)
        
        console.print("\n" + "="*70)
        console.print("🔵 QDRANT VECTOR DATABASE", style="bold blue")
        console.print("="*70)
        console.print(f"Collection: [cyan]{collection_name}[/cyan]")
        console.print(f"Status: [green]{info.status}[/green]")
        console.print(f"Vectors count: [bold yellow]{info.vectors_count}[/bold yellow]")
        console.print(f"Points count: [bold yellow]{info.points_count}[/bold yellow]")
        console.print(f"Dimension: {info.config.params.vectors.size}")
        console.print(f"Distance: {info.config.params.vectors.distance}")
        
        # Sample some points to see what's stored
        if info.points_count > 0:
            console.print(f"\n[dim]Sampling first 5 points to see chunk types...[/dim]")
            points = client.scroll(
                collection_name=collection_name,
                limit=5,
                with_payload=True,
            )[0]
            
            for i, point in enumerate(points, 1):
                payload = point.payload
                chunk_type = payload.get('chunk_type', 'NOT_SET')
                doc_id = payload.get('document_number') or payload.get('id', 'N/A')
                title = payload.get('title', 'N/A')[:60]
                console.print(f"  {i}. chunk_type=[cyan]{chunk_type}[/cyan] | doc=[yellow]{doc_id}[/yellow] | {title}")
        
        client.close()
        return info.points_count
        
    except Exception as e:
        console.print(f"\n❌ Qdrant error: {e}", style="red")
        return 0

async def check_opensearch():
    """Check OpenSearch index stats."""
    try:
        settings = get_settings()
        
        client = OpenSearch(
            hosts=[{'host': settings.opensearch_host, 'port': settings.opensearch_port}],
            http_auth=(settings.opensearch_user, settings.opensearch_password) if settings.opensearch_user else None,
            use_ssl=settings.opensearch_use_ssl,
            verify_certs=settings.opensearch_verify_certs,
        )
        
        index_name = settings.opensearch_index
        
        # Get index stats
        stats = client.indices.stats(index=index_name)
        doc_count = stats['_all']['primaries']['docs']['count']
        
        # Get mapping to see fields
        mapping = client.indices.get_mapping(index=index_name)
        properties = mapping[index_name]['mappings']['properties']
        
        console.print("\n" + "="*70)
        console.print("🟢 OPENSEARCH (BM25)", style="bold green")
        console.print("="*70)
        console.print(f"Index: [cyan]{index_name}[/cyan]")
        console.print(f"Document count: [bold yellow]{doc_count}[/bold yellow]")
        console.print(f"\nFields in mapping:")
        for field in sorted(properties.keys()):
            field_type = properties[field].get('type', 'N/A')
            console.print(f"  - {field}: {field_type}")
        
        # Sample some documents to see chunk types
        if doc_count > 0:
            console.print(f"\n[dim]Sampling first 5 documents to see chunk types...[/dim]")
            search_result = client.search(
                index=index_name,
                body={
                    "query": {"match_all": {}},
                    "size": 5,
                    "_source": ["chunk_type", "document_number", "title", "level"]
                }
            )
            
            for i, hit in enumerate(search_result['hits']['hits'], 1):
                source = hit['_source']
                chunk_type = source.get('chunk_type', 'NOT_SET')
                level = source.get('level', 'N/A')
                doc_id = source.get('document_number', 'N/A')
                title = source.get('title', 'N/A')[:60]
                console.print(f"  {i}. chunk_type=[cyan]{chunk_type}[/cyan] | level=[magenta]{level}[/magenta] | doc=[yellow]{doc_id}[/yellow] | {title}")
        
        client.close()
        return doc_count
        
    except Exception as e:
        console.print(f"\n❌ OpenSearch error: {e}", style="red")
        return 0

async def main():
    console.print("\n" + "="*70)
    console.print("🔍 VERIFYING INDEXED DOCUMENT COUNTS", style="bold yellow")
    console.print("="*70)
    
    qdrant_count = await check_qdrant()
    opensearch_count = await check_opensearch()
    
    console.print("\n" + "="*70)
    console.print("📊 SUMMARY", style="bold cyan")
    console.print("="*70)
    console.print(f"Qdrant vectors:    [bold]{qdrant_count:,}[/bold]")
    console.print(f"OpenSearch docs:   [bold]{opensearch_count:,}[/bold]")
    console.print(f"Difference:        [bold]{abs(qdrant_count - opensearch_count):,}[/bold]")
    
    if qdrant_count == opensearch_count:
        console.print(f"\n✅ Counts match!", style="green")
    else:
        console.print(f"\n⚠️  Counts don't match - possible indexing issue", style="yellow")
    
    # Expected vs actual
    console.print(f"\n[dim]Expected for 50 documents:[/dim]")
    console.print(f"  - If indexing ROOT only: ~50 points")
    console.print(f"  - If indexing ARTICLES: ~1,000-1,500 points (20-30 articles/doc)")
    console.print(f"  - If indexing BOTH: ~1,050-1,550 points")
    
    if qdrant_count > 100:
        console.print(f"\n✅ Articles ARE being indexed! ({qdrant_count} points)")
    else:
        console.print(f"\n❌ Only root documents indexed ({qdrant_count} points)")
        console.print(f"   → Need to implement article-level chunking")
    
    console.print()

if __name__ == "__main__":
    asyncio.run(main())
