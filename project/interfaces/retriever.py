"""
Retriever interface protocol.
"""
from typing import Protocol, runtime_checkable
from project.config.settings import CrawlConfig
from project.schemas.result_schema import RetrievalResult


@runtime_checkable
class Retriever(Protocol):
    """Abstract retrieval protocol enforcing Rule 4 (Dependency Inversion)."""
    async def retrieve(self, url: str, config: CrawlConfig) -> RetrievalResult:
        """Fetches resource at url according to config."""
        ...
