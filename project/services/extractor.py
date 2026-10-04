"""
Content extraction module matching Phase 6 & Section 23 of Implementation Plan.
Implements Extractor interface protocol to isolate primary content and structured data.
"""
from typing import List, Any
from project.interfaces.extractor import Extractor
from project.schemas.result_schema import ParsedDocument, ExtractedContent
from project.utils.logging import logger


class ContentExtractor(Extractor):
    """
    Service responsible for isolating primary article/body content from boilerplate noise.
    """

    def extract(self, parsed: ParsedDocument) -> ExtractedContent:
        """
        Extracts cleaned primary content, headings, tables, links, and media URLs.
        """
        # Filter out trivial or navigational paragraphs
        meaningful_paragraphs: List[str] = []
        for p in parsed.paragraphs:
            cleaned_p = p.strip()
            # Filter out empty or common boilerplate crumbs
            if len(cleaned_p) > 1 and not cleaned_p.lower().startswith(("cookie policy", "terms of use", "privacy policy")):
                meaningful_paragraphs.append(cleaned_p)

        # Assemble primary text content from headings and paragraphs if available, else raw_text
        if meaningful_paragraphs:
            assembled_content = "\n\n".join(meaningful_paragraphs)
        else:
            assembled_content = parsed.raw_text.strip()

        return ExtractedContent(
            title=parsed.title or "",
            headings=parsed.headings,
            paragraphs=meaningful_paragraphs,
            tables=parsed.raw_tables,
            links=parsed.links,
            image_urls=parsed.image_urls,
            pdf_urls=parsed.pdf_urls,
            cleaned_content=assembled_content,
        )
