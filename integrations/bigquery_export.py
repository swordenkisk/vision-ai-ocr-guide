"""
bigquery_export.py - Stream OCR extraction results to a BigQuery data warehouse.

Schema is auto-created on first run. Supports both single-record inserts and
bulk streaming for high-throughput pipelines.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

from google.cloud import bigquery
from google.api_core.exceptions import NotFound

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BigQuery table schema
# ---------------------------------------------------------------------------

OCR_RESULTS_SCHEMA = [
    bigquery.SchemaField("document_uri", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("extracted_text", "STRING"),
    bigquery.SchemaField("confidence", "FLOAT64"),
    bigquery.SchemaField("word_count", "INTEGER"),
    bigquery.SchemaField("processing_time", "TIMESTAMP"),
    bigquery.SchemaField("language", "STRING"),
    bigquery.SchemaField("source_format", "STRING"),
    bigquery.SchemaField("page_count", "INTEGER"),
]


class BigQueryExporter:
    """
    Export OCR results to BigQuery for analytics and auditing.

    Usage:
        exporter = BigQueryExporter(dataset_id="ocr_warehouse", table_id="results")
        exporter.ensure_table_exists()
        exporter.export(results_list)
    """

    def __init__(self, dataset_id: str, table_id: str, project_id: str = None):
        """
        Args:
            dataset_id: BigQuery dataset name.
            table_id:   BigQuery table name.
            project_id: GCP project ID. Defaults to the client's inferred project.
        """
        self.client = bigquery.Client(project=project_id)
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.table_ref = f"{self.client.project}.{dataset_id}.{table_id}"

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------

    def ensure_table_exists(self, schema: list = None) -> bigquery.Table:
        """
        Create the BigQuery table if it does not already exist.

        Args:
            schema: Optional custom schema. Defaults to OCR_RESULTS_SCHEMA.

        Returns:
            The existing or newly created BigQuery Table object.
        """
        try:
            table = self.client.get_table(self.table_ref)
            logger.info(f"Table exists: {self.table_ref}")
            return table
        except NotFound:
            logger.info(f"Creating table: {self.table_ref}")
            dataset_ref = bigquery.DatasetReference(
                self.client.project, self.dataset_id
            )
            try:
                self.client.get_dataset(dataset_ref)
            except NotFound:
                self.client.create_dataset(bigquery.Dataset(dataset_ref))
                logger.info(f"Created dataset: {self.dataset_id}")

            table = bigquery.Table(self.table_ref, schema=schema or OCR_RESULTS_SCHEMA)
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="processing_time",
            )
            return self.client.create_table(table)

    # ------------------------------------------------------------------
    # Export methods
    # ------------------------------------------------------------------

    def export(self, extraction_results: List[dict]) -> int:
        """
        Stream a list of OCR results to BigQuery.

        Args:
            extraction_results: List of dicts as returned by DocumentExtractor.

        Returns:
            Number of rows successfully inserted.

        Raises:
            RuntimeError: If BigQuery reports insert errors.
        """
        if not extraction_results:
            logger.warning("No results to export.")
            return 0

        rows = [self._to_bq_row(r) for r in extraction_results]
        errors = self.client.insert_rows_json(self.table_ref, rows)

        if errors:
            raise RuntimeError(f"BigQuery insert errors: {json.dumps(errors, indent=2)}")

        logger.info(f"Exported {len(rows)} row(s) to {self.table_ref}")
        return len(rows)

    def export_single(self, result: dict) -> None:
        """Convenience wrapper for single-record export."""
        self.export([result])

    def query_recent(self, limit: int = 100) -> List[dict]:
        """
        Fetch the most recently processed documents.

        Args:
            limit: Maximum number of rows to return.

        Returns:
            List of row dictionaries ordered by processing_time descending.
        """
        query = f"""
            SELECT *
            FROM `{self.table_ref}`
            ORDER BY processing_time DESC
            LIMIT {limit}
        """
        results = self.client.query(query).result()
        return [dict(row) for row in results]

    def search_text(self, keyword: str, limit: int = 50) -> List[dict]:
        """
        Full-text search across extracted OCR results.

        Args:
            keyword: Search term (case-insensitive substring match).
            limit:   Maximum rows to return.

        Returns:
            Matching rows as list of dicts.
        """
        query = f"""
            SELECT document_uri, extracted_text, confidence, processing_time
            FROM `{self.table_ref}`
            WHERE LOWER(extracted_text) LIKE LOWER(@keyword)
            ORDER BY processing_time DESC
            LIMIT {limit}
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("keyword", "STRING", f"%{keyword}%")
            ]
        )
        results = self.client.query(query, job_config=job_config).result()
        return [dict(row) for row in results]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _to_bq_row(self, result: dict) -> dict:
        return {
            "document_uri": result.get("source") or result.get("gcs_uri") or "",
            "extracted_text": result.get("text") or "",
            "confidence": result.get("confidence"),
            "word_count": result.get("word_count"),
            "processing_time": result.get(
                "processed_at",
                result.get("timestamp", datetime.utcnow().isoformat()),
            ),
            "language": result.get("detected_language") or result.get("language"),
            "source_format": self._infer_format(result.get("source") or ""),
            "page_count": result.get("page_count", 1),
        }

    @staticmethod
    def _infer_format(uri: str) -> Optional[str]:
        if not uri:
            return None
        ext = uri.rsplit(".", 1)[-1].lower() if "." in uri else ""
        return ext or None


# ---------------------------------------------------------------------------
# Convenience function (matches guide usage)
# ---------------------------------------------------------------------------

def export_to_warehouse(
    extraction_results: list,
    dataset_id: str,
    table_id: str,
    project_id: str = None,
) -> None:
    """
    Stream OCR results to BigQuery analytics warehouse.

    Args:
        extraction_results: List of OCR result dicts.
        dataset_id:         BigQuery dataset name.
        table_id:           BigQuery table name.
        project_id:         GCP project (optional).
    """
    exporter = BigQueryExporter(dataset_id, table_id, project_id)
    exporter.ensure_table_exists()
    exporter.export(extraction_results)
