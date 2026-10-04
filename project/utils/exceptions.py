"""
Custom domain exception hierarchy matching Section 16 of Implementation Plan.
"""

class ProjectError(Exception):
    """Base exception for all system domain errors."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(ProjectError):
    """Raised when URL or configuration validation fails."""
    pass


class RetrievalError(ProjectError):
    """Base exception for network/HTTP retrieval failures."""
    pass


class NetworkError(RetrievalError):
    """DNS or connection level failure."""
    pass


class TimeoutError(RetrievalError):
    """Request timeout exceeded."""
    pass


class HTTPError(RetrievalError):
    """HTTP 4xx/5xx status error."""
    def __init__(self, message: str, status_code: int, details: dict = None):
        super().__init__(message, details)
        self.status_code = status_code


class ParsingError(ProjectError):
    """HTML or PDF parsing failure."""
    pass


class ExtractionError(ProjectError):
    """Content or structural extraction failure."""
    pass


class RenderingError(ProjectError):
    """Playwright browser execution failure."""
    pass


class MediaError(ProjectError):
    """Media download or streaming failure."""
    pass


class PersistenceError(ProjectError):
    """Database read/write/transaction failure."""
    pass


class ExportError(ProjectError):
    """JSON generation or export failure."""
    pass
