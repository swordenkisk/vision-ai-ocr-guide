"""
document_ai_bridge.py - Advanced form and structured document parsing via
Google Cloud Document AI, bridging Vision OCR results with richer entity
extraction for invoices, receipts, and contracts.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from google.cloud import documentai_v1 as documentai
from google.api_core.client_options import ClientOptions

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class DocumentAIBridge:
    """
    Bridge between Vision API OCR and Document AI for structured extraction.

    Document AI goes beyond raw OCR by understanding document semantics:
    - Key-value pairs from forms (e.g., "Invoice Number: INV-1234")
    - Table extraction with header/row structure
    - Named entity recognition (dates, amounts, addresses)
    - Pre-trained processors for invoices, receipts, W-2s, and more

    Pre-built processor types:
        FORM_PARSER_PROCESSOR        - Generic forms with key-value pairs
        INVOICE_PROCESSOR            - Invoices with line items and totals
        RECEIPT_PROCESSOR            - Retail receipts
        IDENTITY_DOCUMENT_PROCESSOR  - Passports, driving licenses
        LENDING_DOCUMENT_SPLIT_AND_CLASSIFY - Mortgage packets
    """

    def __init__(self, project_id: str, location: str, processor_id: str):
        """
        Args:
            project_id:   GCP project ID.
            location:     Processor location ('us' or 'eu').
            processor_id: Document AI processor resource ID.
        """
        self.project_id = project_id
        self.location = location
        self.processor_id = processor_id

        api_endpoint = f"{location}-documentai.googleapis.com"
        self.client = documentai.DocumentProcessorServiceClient(
            client_options=ClientOptions(api_endpoint=api_endpoint)
        )
        self.processor_name = self.client.processor_path(
            project_id, location, processor_id
        )

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def process_document(self, file_path: str, mime_type: str = None) -> dict:
        """
        Process a document using the configured Document AI processor.

        Args:
            file_path: Local path to the document (PDF or image).
            mime_type: Override MIME type detection. Auto-detected if None.

        Returns:
            Structured dictionary with text, fields, tables, and entities.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        mime_type = mime_type or self._infer_mime_type(path)
        logger.info(f"Processing with Document AI: {path.name} [{mime_type}]")

        with open(file_path, "rb") as f:
            raw_document = documentai.RawDocument(
                content=f.read(),
                mime_type=mime_type,
            )

        request = documentai.ProcessRequest(
            name=self.processor_name,
            raw_document=raw_document,
        )

        result = self.client.process_document(request=request)
        document = result.document

        return self._parse_document(document)

    def process_gcs_document(self, gcs_uri: str, mime_type: str) -> dict:
        """
        Process a document stored in Google Cloud Storage.

        Args:
            gcs_uri:   Full GCS URI, e.g. 'gs://bucket/file.pdf'.
            mime_type: MIME type of the document.

        Returns:
            Structured extraction result dictionary.
        """
        logger.info(f"Processing GCS document: {gcs_uri}")

        gcs_document = documentai.GcsDocument(
            gcs_uri=gcs_uri,
            mime_type=mime_type,
        )
        request = documentai.ProcessRequest(
            name=self.processor_name,
            gcs_document=gcs_document,
        )

        result = self.client.process_document(request=request)
        return self._parse_document(result.document)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_document(self, document) -> dict:
        """Convert a Document AI Document proto to a plain dictionary."""
        result = {
            "text": document.text,
            "pages": len(document.pages),
            "form_fields": self._extract_form_fields(document),
            "tables": self._extract_tables(document),
            "entities": self._extract_entities(document),
        }
        return result

    def _extract_form_fields(self, document) -> List[dict]:
        """Extract key-value form field pairs from all pages."""
        fields = []
        for page in document.pages:
            for field in page.form_fields:
                key = self._get_text(field.field_name, document)
                value = self._get_text(field.field_value, document)
                fields.append(
                    {
                        "key": key.strip(),
                        "value": value.strip(),
                        "confidence": field.field_value.confidence,
                    }
                )
        return fields

    def _extract_tables(self, document) -> List[dict]:
        """Extract tables with header and body rows."""
        tables = []
        for page in document.pages:
            for table in page.tables:
                headers = [
                    self._get_text(cell.layout, document).strip()
                    for row in table.header_rows
                    for cell in row.cells
                ]
                body_rows = []
                for row in table.body_rows:
                    body_rows.append(
                        [
                            self._get_text(cell.layout, document).strip()
                            for cell in row.cells
                        ]
                    )
                tables.append({"headers": headers, "rows": body_rows})
        return tables

    def _extract_entities(self, document) -> List[dict]:
        """Extract named entities recognised by the processor."""
        entities = []
        for entity in document.entities:
            entities.append(
                {
                    "type": entity.type_,
                    "mention_text": entity.mention_text,
                    "confidence": entity.confidence,
                    "normalized_value": (
                        entity.normalized_value.text
                        if entity.normalized_value
                        else None
                    ),
                }
            )
        return entities

    @staticmethod
    def _get_text(layout, document) -> str:
        """Reconstruct text from a layout element's text segments."""
        text = ""
        for segment in layout.text_anchor.text_segments:
            start = int(segment.start_index)
            end = int(segment.end_index)
            text += document.text[start:end]
        return text

    @staticmethod
    def _infer_mime_type(path: Path) -> str:
        mime_map = {
            ".pdf":  "application/pdf",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png":  "image/png",
            ".tiff": "image/tiff",
            ".tif":  "image/tiff",
            ".gif":  "image/gif",
            ".bmp":  "image/bmp",
            ".webp": "image/webp",
        }
        return mime_map.get(path.suffix.lower(), "application/octet-stream")
