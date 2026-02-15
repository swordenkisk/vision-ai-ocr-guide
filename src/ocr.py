"""
ocr.py - Core extraction engine for Google Cloud Vision AI OCR.
Handles single document processing with full confidence metrics and spatial data.
"""

from google.cloud import vision
from pathlib import Path
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".pdf"}


class DocumentExtractor:
    """
    Single-document OCR engine using Google Cloud Vision API.
    Supports all Vision-compatible image and PDF formats.
    """

    def __init__(self):
        self.client = vision.ImageAnnotatorClient()

    def extract(self, file_path: str, language: str = "en") -> dict:
        """
        Extract text with confidence metrics and spatial bounding box data.

        Args:
            file_path: Path to the image or document file.
            language:  BCP-47 language code hint (e.g. 'en', 'fr', 'de').

        Returns:
            Dictionary containing extracted text, word count, and bounding boxes.

        Raises:
            ValueError: If the file format is not supported.
            FileNotFoundError: If the file does not exist.
            RuntimeError: If the Vision API returns an error.
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if path.suffix.lower() not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format '{path.suffix}'. "
                f"Supported formats: {', '.join(SUPPORTED_FORMATS)}"
            )

        logger.info(f"Extracting text from: {path.name}")

        with open(file_path, "rb") as f:
            image = vision.Image(content=f.read())

        context = vision.ImageContext(language_hints=[language])
        response = self.client.text_detection(image=image, image_context=context)

        if response.error.message:
            raise RuntimeError(f"Vision API error: {response.error.message}")

        if not response.text_annotations:
            logger.warning(f"No text found in: {path.name}")
            return {"text": "", "confidence": 0, "word_count": 0, "bounding_boxes": []}

        full_text = response.text_annotations[0]

        result = {
            "text": full_text.description,
            "confidence": getattr(full_text, "score", None),
            "word_count": len(response.text_annotations) - 1,
            "bounding_boxes": [
                {
                    "text": word.description,
                    "vertices": [(v.x, v.y) for v in word.bounding_poly.vertices],
                    "confidence": getattr(word, "score", None),
                }
                for word in response.text_annotations[1:]
            ],
        }

        logger.info(f"Extracted {result['word_count']} words from {path.name}")
        return result

    def extract_document(self, file_path: str, language: str = "en") -> dict:
        """
        Extract text using DOCUMENT_TEXT_DETECTION for dense/structured documents.
        Preferred for invoices, forms, and multi-column layouts.

        Args:
            file_path: Path to the image or document file.
            language:  BCP-47 language code hint.

        Returns:
            Dictionary with full text, page metadata, and block-level structure.
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Running document text detection on: {path.name}")

        with open(file_path, "rb") as f:
            image = vision.Image(content=f.read())

        context = vision.ImageContext(language_hints=[language])
        response = self.client.document_text_detection(image=image, image_context=context)

        if response.error.message:
            raise RuntimeError(f"Vision API error: {response.error.message}")

        annotation = response.full_text_annotation

        pages = []
        for page in annotation.pages:
            detected_langs = []
            if page.property and page.property.detected_languages:
                detected_langs = [
                    {"language_code": dl.language_code, "confidence": dl.confidence}
                    for dl in page.property.detected_languages
                ]

            pages.append(
                {
                    "width": page.width,
                    "height": page.height,
                    "block_count": len(page.blocks),
                    "confidence": page.confidence,
                    "detected_languages": detected_langs,
                }
            )

        return {
            "text": annotation.text,
            "pages": pages,
            "page_count": len(pages),
        }

    def save_result(self, result: dict, output_path: str):
        """Persist extraction result to a JSON file."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Result saved to: {output_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ocr.py <image_path> [language_code]")
        print("  Example: python ocr.py samples/invoice.jpg en")
        sys.exit(1)

    file_path = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "en"

    extractor = DocumentExtractor()
    result = extractor.extract(file_path, language=language)

    print(f"\n--- Extracted Text ---\n{result['text']}")
    print(f"\n--- Stats ---")
    print(f"Words found : {result['word_count']}")
    print(f"Confidence  : {result['confidence']}")
