"""Web search tool for supplementary legal knowledge using DuckDuckGo."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WebSearchResult:
    """Result from a web search."""
    title: str
    snippet: str
    url: str
    source: str  # domain name


@dataclass
class CacheEntry:
    """Cache entry with TTL."""
    results: list[WebSearchResult]
    timestamp: float


class WebSearchTool:
    """Web search for supplementary legal knowledge using DuckDuckGo."""
    
    def __init__(self, cache_ttl_seconds: float = 3600.0, timeout_seconds: float = 5.0):
        """Initialize the web search tool.
        
        Args:
            cache_ttl_seconds: Time-to-live for cache entries in seconds (default: 1 hour)
            timeout_seconds: Maximum time to wait for search results (default: 5 seconds)
        """
        self._cache: dict[str, CacheEntry] = {}
        self._cache_ttl = cache_ttl_seconds
        self._timeout = timeout_seconds
        self._ddgs = None  # Lazy init
    
    def _get_ddgs(self) -> Any:
        """Lazy-init DuckDuckGo search client."""
        if self._ddgs is None:
            try:
                # Try new package name first (ddgs), fallback to old (duckduckgo_search)
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS
                self._ddgs = DDGS()
            except ImportError:
                logger.error("Web search library not installed. Run: pip install ddgs")
                raise
        return self._ddgs
    
    def _get_cache_key(self, query: str, num_results: int, site_filter: str | None = None) -> str:
        """Generate cache key for a search query."""
        return f"{query}:{num_results}:{site_filter or ''}"
    
    def _get_cached_results(self, cache_key: str) -> list[WebSearchResult] | None:
        """Get cached results if not expired."""
        if cache_key not in self._cache:
            return None
        
        entry = self._cache[cache_key]
        if time.time() - entry.timestamp > self._cache_ttl:
            # Expired, remove from cache
            del self._cache[cache_key]
            return None
        
        logger.debug(f"Cache hit for key: {cache_key}")
        return entry.results
    
    def _cache_results(self, cache_key: str, results: list[WebSearchResult]) -> None:
        """Cache search results."""
        self._cache[cache_key] = CacheEntry(
            results=results,
            timestamp=time.time()
        )
    
    def _extract_source(self, url: str) -> str:
        """Extract domain name from URL."""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower().replace("www.", "")
        except Exception:
            return "unknown"
    
    async def search(self, query: str, num_results: int = 3) -> list[WebSearchResult]:
        """Search the web for legal information.
        
        Args:
            query: Search query string
            num_results: Number of results to return (default: 3)
            
        Returns:
            List of WebSearchResult objects. Returns empty list on error.
        """
        cache_key = self._get_cache_key(query, num_results)
        
        # Check cache first
        cached = self._get_cached_results(cache_key)
        if cached is not None:
            return cached
        
        try:
            # Run search with timeout
            results = await asyncio.wait_for(
                self._do_search(query, num_results),
                timeout=self._timeout
            )
            
            # Cache successful results
            self._cache_results(cache_key, results)
            return results
            
        except asyncio.TimeoutError:
            logger.warning(f"Web search timed out after {self._timeout}s for query: {query[:50]}...")
            return []
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
            return []
    
    async def _do_search(self, query: str, num_results: int) -> list[WebSearchResult]:
        """Execute the actual search (runs in thread pool)."""
        loop = asyncio.get_event_loop()
        
        def _search():
            ddgs = self._get_ddgs()
            results = []
            
            # Use text() method for search
            search_results = ddgs.text(query, max_results=num_results)
            
            for result in search_results:
                title = result.get("title", "")
                snippet = result.get("body", "")
                url = result.get("href", "")
                
                if title and url:
                    results.append(WebSearchResult(
                        title=title,
                        snippet=snippet,
                        url=url,
                        source=self._extract_source(url)
                    ))
            
            return results
        
        return await loop.run_in_executor(None, _search)
    
    async def search_vietnamese_law(self, query: str, num_results: int = 3) -> list[WebSearchResult]:
        """Specialized search targeting Vietnamese legal sources.
        
        Adds Vietnamese legal site prefixes to prioritize relevant sources.
        
        Args:
            query: Search query string
            num_results: Number of results to return (default: 3)
            
        Returns:
            List of WebSearchResult objects from Vietnamese legal sources.
            Returns empty list on error.
        """
        # Vietnamese legal site prefixes
        vietnamese_sites = [
            "thuvienphapluat.vn",
            "luatvietnam.vn",
            "phapluat.suckhoedoisong.vn",
            "baophapluat.vn",
            "phapluat.tuoitre.vn",
        ]
        
        # Build site-restricted query
        site_restrictions = " OR ".join(f"site:{site}" for site in vietnamese_sites)
        enhanced_query = f"({query}) ({site_restrictions})"
        
        cache_key = self._get_cache_key(query, num_results, "vietnamese_law")
        
        # Check cache first
        cached = self._get_cached_results(cache_key)
        if cached is not None:
            return cached
        
        try:
            # Run search with timeout
            results = await asyncio.wait_for(
                self._do_search(enhanced_query, num_results),
                timeout=self._timeout
            )
            
            # Cache successful results
            self._cache_results(cache_key, results)
            return results
            
        except asyncio.TimeoutError:
            logger.warning(f"Vietnamese law search timed out after {self._timeout}s")
            return []
        except Exception as e:
            logger.warning(f"Vietnamese law search failed: {e}")
            return []
    
    def clear_cache(self) -> None:
        """Clear the search cache."""
        self._cache.clear()
        logger.debug("Web search cache cleared")
    
    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache size and other stats
        """
        return {
            "cache_size": len(self._cache),
            "cache_ttl_seconds": self._cache_ttl,
            "timeout_seconds": self._timeout,
        }
