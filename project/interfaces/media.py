"""
Media downloader interface protocol.
"""
from typing import Protocol, runtime_checkable
from project.schemas.page_schema import MediaReference


@runtime_checkable
class MediaDownloader(Protocol):
    """Abstract media downloading protocol."""
    async def download(self, media: MediaReference, job_id: str) -> MediaReference:
        """Streams media asset to filesystem and updates metadata with file path and size."""
        ...
