"""
Parser interface protocol for document parsing.
"""
from typing import Protocol, runtime_checkable
from project.schemas.result_schema import RetrievalResult, ParsedDocument


@runtime_checkable
class Parser(Protocol):
    """Abstract parsing protocol for HTML and PDF structures."""
    def parse(self, document: RetrievalResult) -> ParsedDocument:
        """Parses retrieved document bytes/text into structural components."""
        ...
