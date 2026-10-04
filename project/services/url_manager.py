"""
URL Manager service module matching Phase 2 & Section 8/9 of Technical Implementation Plan.
Coordinates BFS frontier queue, link discovery deduplication, and crawl depth boundaries.
"""
from collections import deque
from typing import List, Optional, Set
from project.schemas.url_schema import CrawlURL
from project.utils.url_normalizer import normalize_url, is_valid_url
from project.utils.logging import logger


class URLManager:
    """
    In-memory URL frontier and state coordinator for BFS crawling.
    Enforces URL deduplication, depth ceilings, and non-recursive constraints.
    """

    def __init__(self, max_depth: Optional[int] = None, recursive: bool = True):
        self._queue: deque[CrawlURL] = deque()
        self._seen_normalized: Set[str] = set()
        self._total_discovered: int = 0
        self.max_depth = max_depth
        self.recursive = recursive

    @property
    def total_discovered(self) -> int:
        """Property returning total discovered count."""
        return self._total_discovered

    def has_next(self) -> bool:
        """Alias for has_urls."""
        return self.has_urls()

    def get_next(self) -> Optional[CrawlURL]:
        """Alias for pop_next_url."""
        return self.pop_next_url()

    def add_url(
        self,
        raw_url: str,
        depth: int = 0,
        base_url: Optional[str] = None,
        parent_url_id: Optional[str] = None,
    ) -> Optional[CrawlURL]:
        """
        Convenience method to add either a seed (depth 0) or child URL.
        """
        if depth == 0:
            return self.add_seed(raw_url, parent_url_id=parent_url_id)

        limit = self.max_depth if self.max_depth is not None else depth
        items = self.add_discovered_links(
            parent_depth=depth - 1,
            links=[raw_url],
            max_depth=limit,
            recursive=self.recursive,
            parent_url_id=parent_url_id,
        )
        return items[0] if items else None

    def is_visited(self, normalized_url: str) -> bool:
        """Returns True if the normalized URL has already been queued or visited."""
        return normalized_url in self._seen_normalized

    def mark_visited(self, normalized_url: str) -> None:
        """Explicitly records a normalized URL as seen."""
        self._seen_normalized.add(normalized_url)

    def add_seed(self, raw_url: str, parent_url_id: Optional[str] = None) -> Optional[CrawlURL]:
        """
        Validates, normalizes, and enqueues a seed URL at depth 0.
        """
        if not is_valid_url(raw_url):
            logger.warning(f"Rejecting invalid seed URL: {raw_url}")
            return None

        try:
            norm_url = normalize_url(raw_url)
        except Exception as exc:
            logger.warning(f"Normalization failed for seed {raw_url}: {exc}")
            return None

        if norm_url in self._seen_normalized:
            logger.info(f"Duplicate seed skipped: {norm_url}")
            return None

        self._seen_normalized.add(norm_url)
        self._total_discovered += 1

        crawl_item = CrawlURL(
            url=raw_url,
            normalized_url=norm_url,
            depth=0,
            parent_url_id=parent_url_id,
        )
        self._queue.append(crawl_item)
        return crawl_item

    def add_seeds(self, urls: List[str]) -> List[CrawlURL]:
        """Enqueues multiple seed URLs, ignoring duplicates."""
        added = []
        for url in urls:
            item = self.add_seed(url)
            if item:
                added.append(item)
        return added

    def add_discovered_links(
        self,
        parent_depth: int,
        links: List[str],
        max_depth: int,
        recursive: bool,
        parent_url_id: Optional[str] = None,
    ) -> List[CrawlURL]:
        """
        Processes discovered hyperlinks from a crawled page:
        - If recursive is False, new links are discarded.
        - Checks parent_depth + 1 <= max_depth.
        - Deduplicates against previously seen URLs.
        """
        if not recursive:
            return []

        next_depth = parent_depth + 1
        if next_depth > max_depth:
            return []

        added_links: List[CrawlURL] = []
        for link in links:
            if not is_valid_url(link):
                continue

            try:
                norm_link = normalize_url(link)
            except Exception:
                continue

            if norm_link in self._seen_normalized:
                continue

            self._seen_normalized.add(norm_link)
            self._total_discovered += 1

            crawl_url = CrawlURL(
                url=link,
                normalized_url=norm_link,
                depth=next_depth,
                parent_url_id=parent_url_id,
            )
            self._queue.append(crawl_url)
            added_links.append(crawl_url)

        return added_links

    def pop_next_url(self) -> Optional[CrawlURL]:
        """Pops and returns the next CrawlURL in BFS order."""
        if self._queue:
            return self._queue.popleft()
        return None

    def has_urls(self) -> bool:
        """Returns True if there are remaining URLs in the frontier queue."""
        return len(self._queue) > 0

    def queue_size(self) -> int:
        """Returns current number of pending URLs in queue."""
        return len(self._queue)

    def total_discovered_count(self) -> int:
        """Returns total unique URLs discovered and queued since creation."""
        return self._total_discovered

    def clear(self) -> None:
        """Resets the queue and visited state."""
        self._queue.clear()
        self._seen_normalized.clear()
        self._total_discovered = 0
