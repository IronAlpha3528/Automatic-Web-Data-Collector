"""
Renderer interface protocol for dynamic JavaScript execution.
"""
from typing import Protocol, runtime_checkable
from project.config.settings import CrawlConfig
from project.schemas.result_schema import RetrievalResult


@runtime_checkable
class Renderer(Protocol):
    """Abstract dynamic browser rendering protocol."""
    async def render(self, url: str, config: CrawlConfig) -> RetrievalResult:
        """Renders page via browser runtime and returns resulting DOM."""
        ...

    async def close(self) -> None:
        """Cleans up browser contexts and runtime."""
        ...
