"""
JSON Export module matching Phase 10 & Section 33 of Implementation Plan.
Generates structured, validated JSON files conforming strictly to Appendix B schema.
"""
import os
import json
import tempfile
from typing import List, Optional, Union
from project.schemas.page_schema import ProcessedDocument
from project.config.settings import settings
from project.utils.exceptions import ExportError
from project.utils.logging import logger


class JSONExporter:
    """
    Service responsible for serializing crawled and preprocessed documents to structured JSON.
    """

    def __init__(self, base_output_dir: Optional[str] = None):
        self.base_output_dir = base_output_dir or settings.output_dir

    def _get_job_json_dir(self, job_id: str) -> str:
        """Constructs and ensures the directory path for job JSON exports."""
        json_dir = os.path.join(self.base_output_dir, "jobs", job_id, "json")
        os.makedirs(json_dir, exist_ok=True)
        return json_dir

    def serialize_document(self, document: ProcessedDocument) -> dict:
        """Serializes a single ProcessedDocument model to a validated dictionary."""
        try:
            return document.model_dump()
        except Exception as exc:
            raise ExportError(f"Failed to serialize document {document.url}: {exc}") from exc

    def serialize_documents(self, documents: List[ProcessedDocument]) -> List[dict]:
        """Serializes a list of ProcessedDocument models."""
        return [self.serialize_document(doc) for doc in documents]

    def export_job_results(
        self,
        job_id: str,
        documents: List[ProcessedDocument],
        filename: Optional[str] = None,
        custom_dir: Optional[str] = None,
    ) -> str:
        """
        Exports a collection of ProcessedDocuments for a job to an atomic JSON file.

        Args:
            job_id: Scraping job identifier.
            documents: List of ProcessedDocument instances.
            filename: Optional custom filename (defaults to '{job_id}_results.json').
            custom_dir: Optional target directory override.

        Returns:
            The absolute path of the written JSON file.

        Raises:
            ExportError: If JSON serialization, schema validation, or disk write fails.
        """
        target_dir = custom_dir or self._get_job_json_dir(job_id)
        os.makedirs(target_dir, exist_ok=True)

        target_file_name = filename or f"{job_id}_results.json"
        target_path = os.path.join(target_dir, target_file_name)

        try:
            data = self.serialize_documents(documents)
            json_str = json.dumps(data, indent=2, ensure_ascii=False)

            # Atomic write: write to temp file in the same directory then rename
            temp_fd, temp_path = tempfile.mkstemp(dir=target_dir, prefix="export_", suffix=".tmp")
            try:
                with open(temp_fd, "w", encoding="utf-8") as f:
                    f.write(json_str)
                # Atomic replace
                if os.path.exists(target_path):
                    os.replace(temp_path, target_path)
                else:
                    os.rename(temp_path, target_path)
            except Exception:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                raise

            logger.info(f"Successfully exported {len(documents)} document(s) to {target_path}")
            return os.path.abspath(target_path)

        except Exception as exc:
            logger.error(f"Failed to export JSON results for job {job_id}: {exc}")
            raise ExportError(f"Export failed for job {job_id}: {exc}") from exc

    def export_dataset(self, documents: List[ProcessedDocument], job_id: str) -> str:
        """Alias for export_job_results conforming to JobManager interface."""
        return self.export_job_results(job_id=job_id, documents=documents)

    def export_single_document(
        self,
        job_id: str,
        document: ProcessedDocument,
        filename: Optional[str] = None,
    ) -> str:
        """Exports a single ProcessedDocument to an individual JSON file."""
        target_dir = self._get_job_json_dir(job_id)
        target_file_name = filename or f"page_{document.metadata.content_hash[:12]}.json"
        target_path = os.path.join(target_dir, target_file_name)

        try:
            data = self.serialize_document(document)
            json_str = json.dumps(data, indent=2, ensure_ascii=False)

            temp_fd, temp_path = tempfile.mkstemp(dir=target_dir, prefix="page_", suffix=".tmp")
            try:
                with open(temp_fd, "w", encoding="utf-8") as f:
                    f.write(json_str)
                os.replace(temp_path, target_path)
                return os.path.abspath(target_path)
            except Exception:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                raise
        except Exception as exc:
            raise ExportError(f"Failed to export document {document.url}: {exc}") from exc
