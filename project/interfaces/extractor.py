"""
Extractor interface protocol for primary content extraction.
"""
from typing import Protocol, runtime_checkable
from project.schemas.result_schema import ParsedDocument, ExtractedContent


@runtime_checkable
class Extractor(Protocol):
    """Abstract extraction protocol isolating primary body content from noise."""
    def extract(self, parsed: ParsedDocument) -> ExtractedContent:
        """Extracts cleaned content, headings, and tables from parsed DOM."""
        ...
