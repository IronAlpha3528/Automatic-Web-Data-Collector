"""
MediaDownloader service for streaming and saving binary images and PDFs.
Conforms to project.interfaces.media.MediaDownloader protocol.
"""
import os
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional
import httpx

from project.schemas.page_schema import MediaReference
from project.config.settings import settings
from project.utils.logging import logger


class DefaultMediaDownloader:
    """
    Asynchronously downloads media assets (images, PDFs) and persists to disk.
    Directory layout matches Section 3 Storage layout:
    output/jobs/<job_id>/images/
    output/jobs/<job_id>/pdfs/
    """

    def __init__(
        self,
        base_output_dir: Optional[str] = None,
        timeout: int = 15,
        max_bytes: int = 25 * 1024 * 1024,  # 25 MB safety ceiling
    ):
        self.base_output_dir = Path(base_output_dir or settings.output_dir)
        self.timeout = timeout
        self.max_bytes = max_bytes

    def _resolve_extension(self, url: str, content_type: Optional[str], default_type: str) -> str:
        """Determines proper file extension from URL or MIME type."""
        # Check URL path
        url_path = url.split("?")[0].split("#")[0]
        ext = Path(url_path).suffix.lower()
        if ext and len(ext) <= 5:
            return ext

        # Check content-type header
        if content_type:
            mime = content_type.split(";")[0].strip().lower()
            guessed = mimetypes.guess_extension(mime)
            if guessed:
                return guessed

        return ".pdf" if default_type == "pdf" else ".jpg"

    async def download(self, media: MediaReference, job_id: str) -> MediaReference:
        """
        Streams binary media, writes to job output directory, and updates MediaReference.
        Does not crash on failure; isolates URL-level failure by setting status='failed'.
        """
        subfolder = "pdfs" if media.media_type.lower() == "pdf" else "images"
        target_dir = self.base_output_dir / "jobs" / job_id / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)

        url_hash = hashlib.sha256(media.url.encode("utf-8")).hexdigest()[:16]

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            ) as client:
                async with client.stream("GET", media.url) as response:
                    if response.status_code >= 400:
                        logger.warning(
                            f"Failed media download for {media.url}: HTTP {response.status_code}"
                        )
                        media.status = "failed"
                        return media

                    content_type = response.headers.get("content-type")
                    ext = self._resolve_extension(media.url, content_type, media.media_type)
                    filename = f"{url_hash}{ext}"
                    filepath = target_dir / filename

                    total_bytes = 0
                    with open(filepath, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            total_bytes += len(chunk)
                            if total_bytes > self.max_bytes:
                                logger.warning(
                                    f"Media file {media.url} exceeded max size limit of {self.max_bytes} bytes"
                                )
                                media.status = "failed"
                                filepath.unlink(missing_ok=True)
                                return media
                            f.write(chunk)

                    media.local_path = str(filepath.relative_to(self.base_output_dir).as_posix())
                    media.file_size = total_bytes
                    media.status = "downloaded"
                    logger.debug(f"Saved media {media.url} -> {media.local_path} ({total_bytes} bytes)")
                    return media

        except Exception as exc:
            logger.warning(f"Error downloading media from {media.url}: {exc}")
            if "filepath" in locals() and isinstance(filepath, Path):
                filepath.unlink(missing_ok=True)
            media.status = "failed"
            return media
