"""
gcs_loader.py - Google Cloud Storage connector for Vision AI OCR.

Provides:
- Triggered Cloud Function handler (GCS → OCR → GCS)
- Batch download helper for processing GCS-hosted documents locally
- Direct GCS URI OCR (no download required)
"""

import json
import logging
from datetime import datetime
from typing import List

from google.cloud import storage, vision

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cloud Function entry point
# ---------------------------------------------------------------------------

def gcs_ocr_trigger(event: dict, context) -> None:
    """
    Cloud Function triggered automatically on GCS object upload.

    Deploy with:
        gcloud functions deploy gcs_ocr_trigger \\
          --runtime python311 \\
          --trigger-resource YOUR_BUCKET \\
          --trigger-event google.storage.object.finalize

    Args:
        event:   GCS event payload containing bucket name and file name.
        context: Cloud Function execution context (includes timestamp).
    """
    bucket_name: str = event["bucket"]
    file_name: str = event["name"]

    # Prevent infinite loops triggered by writing output files
    if file_name.startswith("processed/"):
        logger.info(f"Skipping already-processed file: {file_name}")
        return

    logger.info(f"Processing: gs://{bucket_name}/{file_name}")

    vision_client = vision.ImageAnnotatorClient()
    storage_client = storage.Client()

    # Reference the file directly in GCS — no download needed
    image = vision.Image(
        source=vision.ImageSource(
            gcs_image_uri=f"gs://{bucket_name}/{file_name}"
        )
    )

    response = vision_client.text_detection(image=image)

    if response.error.message:
        logger.error(f"Vision API error for {file_name}: {response.error.message}")
        return

    extracted_text = (
        response.text_annotations[0].description
        if response.text_annotations
        else ""
    )

    result = {
        "source": file_name,
        "bucket": bucket_name,
        "text": extracted_text,
        "word_count": len(extracted_text.split()) if extracted_text else 0,
        "timestamp": context.timestamp,
        "processed_at": datetime.utcnow().isoformat(),
    }

    output_blob_name = f"processed/{file_name}.json"
    bucket = storage_client.bucket(bucket_name)
    output_blob = bucket.blob(output_blob_name)
    output_blob.upload_from_string(
        json.dumps(result, indent=2),
        content_type="application/json",
    )

    logger.info(f"Result written to: gs://{bucket_name}/{output_blob_name}")


# ---------------------------------------------------------------------------
# GCS URI direct OCR
# ---------------------------------------------------------------------------

class GCSDocumentProcessor:
    """
    Process documents stored in Google Cloud Storage without downloading them.
    """

    def __init__(self):
        self.vision_client = vision.ImageAnnotatorClient()
        self.storage_client = storage.Client()

    def extract_from_gcs(self, gcs_uri: str, language: str = "en") -> dict:
        """
        Run OCR on a GCS-hosted image using its URI directly.

        Args:
            gcs_uri:  Full GCS URI, e.g. 'gs://my-bucket/documents/scan.jpg'.
            language: BCP-47 language hint.

        Returns:
            Dictionary with extracted text and metadata.
        """
        logger.info(f"Extracting from GCS URI: {gcs_uri}")

        image = vision.Image(
            source=vision.ImageSource(gcs_image_uri=gcs_uri)
        )
        context = vision.ImageContext(language_hints=[language])
        response = self.vision_client.text_detection(image=image, image_context=context)

        if response.error.message:
            raise RuntimeError(f"Vision API error: {response.error.message}")

        text = (
            response.text_annotations[0].description
            if response.text_annotations
            else ""
        )

        return {
            "gcs_uri": gcs_uri,
            "text": text,
            "word_count": len(text.split()) if text else 0,
        }

    def batch_extract_from_bucket(
        self,
        bucket_name: str,
        prefix: str = "",
        output_bucket: str = None,
        output_prefix: str = "ocr-results/",
    ) -> List[dict]:
        """
        Process all supported images in a GCS bucket (or prefix/folder).

        Args:
            bucket_name:   Source bucket name.
            prefix:        Optional folder prefix to filter files.
            output_bucket: Bucket to write results to (defaults to same bucket).
            output_prefix: Prefix for output JSON files.

        Returns:
            List of extraction result dictionaries.
        """
        SUPPORTED = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}

        bucket = self.storage_client.bucket(bucket_name)
        blobs = [
            b for b in bucket.list_blobs(prefix=prefix)
            if any(b.name.lower().endswith(ext) for ext in SUPPORTED)
        ]

        logger.info(f"Found {len(blobs)} image(s) in gs://{bucket_name}/{prefix}")

        out_bucket_name = output_bucket or bucket_name
        out_bucket = self.storage_client.bucket(out_bucket_name)

        results = []
        for blob in blobs:
            gcs_uri = f"gs://{bucket_name}/{blob.name}"
            try:
                result = self.extract_from_gcs(gcs_uri)
                results.append(result)

                out_name = f"{output_prefix}{blob.name}.json"
                out_blob = out_bucket.blob(out_name)
                out_blob.upload_from_string(
                    json.dumps(result, indent=2),
                    content_type="application/json",
                )
                logger.info(f"✓ {blob.name}")
            except Exception as exc:
                logger.error(f"✗ {blob.name}: {exc}")

        return results
