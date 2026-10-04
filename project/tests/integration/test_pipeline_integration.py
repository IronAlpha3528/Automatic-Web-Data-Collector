"""
Integration tests matching Phase 13 & Section 49 of Technical Implementation Plan.
Verifies inter-service pipelines: Retriever -> Parser -> Extractor -> Preprocessor -> JSONExporter.
"""
import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from project.config.settings import CrawlConfig
from project.services.retriever import HTTPXRetriever
from project.services.parser import DocumentParser
from project.services.extractor import ContentExtractor
from project.services.preprocessor import ContentPreprocessor
from project.services.json_exporter import JSONExporter


class TestPipelineIntegration:
    """End-to-end processing pipeline integration tests."""

    @pytest.mark.anyio
    async def test_full_text_document_processing_pipeline(self, tmp_path):
        """
        Executes complete flow:
        Mocked HTTP Retrieval -> Structural Parser -> Extractor -> Preprocessor -> JSON Export
        """
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Integration Test Page</title>
        </head>
        <body>
            <h1>Main Research Header</h1>
            <p>First paragraph explaining the methodology and algorithms.</p>
            <h2>Results Summary</h2>
            <p>Second paragraph presenting the findings.</p>
            <table>
                <tr><th>Metric</th><th>Score</th></tr>
                <tr><td>Accuracy</td><td>98.5%</td></tr>
            </table>
            <a href="/dataset.pdf">Download Full Dataset</a>
            <img src="/figures/fig1.png" alt="Figure 1">
        </body>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
        mock_resp.text = sample_html
        mock_resp.url = "https://example.org/research/paper1"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        # 1. Retrieval
        retriever = HTTPXRetriever(client=mock_client)
        config = CrawlConfig()
        retrieval_result = await retriever.retrieve("https://example.org/research/paper1", config)
        assert retrieval_result.success is True

        # 2. Parsing
        parser = DocumentParser()
        parsed_doc = parser.parse(retrieval_result)
        assert parsed_doc.title == "Integration Test Page"
        assert len(parsed_doc.headings) == 2
        assert len(parsed_doc.paragraphs) == 2
        assert len(parsed_doc.raw_tables) == 1

        # 3. Extraction
        extractor = ContentExtractor()
        extracted = extractor.extract(parsed_doc)
        assert extracted.title == "Integration Test Page"
        assert len(extracted.paragraphs) == 2
        assert "methodology" in extracted.cleaned_content

        # 4. Preprocessing
        preprocessor = ContentPreprocessor()
        processed_doc = preprocessor.preprocess(
            extracted=extracted,
            job_id="JOB-INTEG-1",
            url=retrieval_result.url,
            crawl_depth=1,
        )
        assert processed_doc.job_id == "JOB-INTEG-1"
        assert processed_doc.metadata.content_hash is not None
        assert len(processed_doc.images) == 1
        assert len(processed_doc.documents) == 1
        assert processed_doc.documents[0].url == "https://example.org/dataset.pdf"

        # 5. JSON Export
        exporter = JSONExporter(base_output_dir=str(tmp_path))
        export_file = exporter.export_job_results(
            job_id="JOB-INTEG-1",
            documents=[processed_doc],
        )

        assert os.path.isfile(export_file)
        with open(export_file, "r", encoding="utf-8") as f:
            exported_data = json.load(f)

        assert len(exported_data) == 1
        record = exported_data[0]
        assert record["job_id"] == "JOB-INTEG-1"
        assert record["url"] == "https://example.org/research/paper1"
        assert record["title"] == "Integration Test Page"
        assert record["headings"] == ["Main Research Header", "Results Summary"]
        assert record["metadata"]["crawl_depth"] == 1
        assert record["metadata"]["status"] == "success"
