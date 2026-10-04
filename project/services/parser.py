"""
Document parser module matching Phase 5 & Section 22/27 of Implementation Plan.
Implements the Parser interface protocol for HTML and PDF content.
"""
import io
from urllib.parse import urljoin
from typing import List, Any
from bs4 import BeautifulSoup

from project.interfaces.parser import Parser
from project.schemas.result_schema import RetrievalResult, ParsedDocument
from project.schemas.page_schema import DocumentLink
from project.utils.exceptions import ParsingError
from project.utils.logging import logger


class DocumentParser(Parser):
    """
    Parser service that extracts structural components from HTML documents and PDF files.
    """

    def _is_pdf(self, document: RetrievalResult) -> bool:
        """Determines if the document is a PDF asset."""
        if document.content_type and "application/pdf" in document.content_type.lower():
            return True
        if document.url and document.url.lower().split("?")[0].endswith(".pdf"):
            return True
        if isinstance(document.content, bytes) and document.content.startswith(b"%PDF-"):
            return True
        return False

    def _parse_html(self, html_text: str, base_url: str) -> ParsedDocument:
        """Parses HTML DOM with BeautifulSoup and lxml/html.parser."""
        try:
            soup = BeautifulSoup(html_text, "lxml")
        except Exception:
            soup = BeautifulSoup(html_text, "html.parser")

        # 1. Extract Title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # 2. Extract Headings (h1 - h6)
        headings: List[str] = []
        for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            text = h.get_text(strip=True)
            if text:
                headings.append(text)

        # 3. Extract Paragraphs
        paragraphs: List[str] = []
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if text:
                paragraphs.append(text)

        # 4. Extract Tables
        raw_tables: List[Any] = []
        for table in soup.find_all("table"):
            table_data = []
            for row in table.find_all("tr"):
                row_data = [cell.get_text(strip=True) for cell in row.find_all(["th", "td"])]
                if row_data:
                    table_data.append(row_data)
            if table_data:
                raw_tables.append(table_data)

        # 5. Extract Links, Images, and PDF references
        links: List[DocumentLink] = []
        pdf_urls: List[str] = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            abs_url = urljoin(base_url, href)
            link_text = a.get_text(strip=True)
            links.append(DocumentLink(url=abs_url, text=link_text))
            
            clean_href = href.split("?")[0].lower()
            if clean_href.endswith(".pdf"):
                if abs_url not in pdf_urls:
                    pdf_urls.append(abs_url)

        image_urls: List[str] = []
        for img in soup.find_all("img", src=True):
            src = img.get("src", "").strip()
            if not src or src.startswith("data:"):
                continue
            abs_img_url = urljoin(base_url, src)
            if abs_img_url not in image_urls:
                image_urls.append(abs_img_url)

        # 6. Extract Raw Visible Text
        body = soup.find("body") or soup
        # Work on a copy for text extraction without scripts/styles
        for script_or_style in body(["script", "style", "noscript"]):
            script_or_style.extract()
        raw_text = body.get_text(separator="\n", strip=True)

        return ParsedDocument(
            url=base_url,
            title=title,
            headings=headings,
            paragraphs=paragraphs,
            raw_tables=raw_tables,
            links=links,
            image_urls=image_urls,
            pdf_urls=pdf_urls,
            raw_text=raw_text,
        )

    def _parse_pdf(self, content: bytes, base_url: str) -> ParsedDocument:
        """Parses PDF document using PyMuPDF (fitz)."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
            title = doc.metadata.get("title", "") or ""
            paragraphs: List[str] = []
            full_text_parts: List[str] = []

            for page in doc:
                text = page.get_text()
                if text.strip():
                    page_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                    paragraphs.extend(page_paragraphs)
                    full_text_parts.append(text.strip())

            doc.close()
            raw_text = "\n\n".join(full_text_parts)

            return ParsedDocument(
                url=base_url,
                title=title,
                headings=[],
                paragraphs=paragraphs,
                raw_tables=[],
                links=[],
                image_urls=[],
                pdf_urls=[],
                raw_text=raw_text,
            )
        except Exception as exc:
            logger.error(f"Failed to parse PDF document at {base_url}: {exc}")
            raise ParsingError(f"PDF parsing failure: {exc}") from exc

    def parse(self, document: RetrievalResult) -> ParsedDocument:
        """
        Parses retrieved document into structured ParsedDocument.
        """
        if not document.success or document.content is None:
            return ParsedDocument(
                url=document.url,
                title="",
                headings=[],
                paragraphs=[],
                raw_tables=[],
                links=[],
                image_urls=[],
                pdf_urls=[],
                raw_text="",
            )

        if self._is_pdf(document):
            if isinstance(document.content, str):
                content_bytes = document.content.encode("utf-8")
            else:
                content_bytes = document.content
            return self._parse_pdf(content_bytes, document.url)
        else:
            if isinstance(document.content, bytes):
                html_text = document.content.decode("utf-8", errors="replace")
            else:
                html_text = document.content
            return self._parse_html(html_text, document.url)
