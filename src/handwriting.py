"""
handwriting.py - Specialized pipeline for cursive and printed handwriting recognition.
Uses DOCUMENT_TEXT_DETECTION which performs better on handwritten content than
the standard text_detection endpoint.
"""

import json
import logging
from pathlib import Path

from google.cloud import vision

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class HandwritingExtractor:
    """
    Optimized OCR pipeline for handwritten documents.

    DOCUMENT_TEXT_DETECTION is preferred over TEXT_DETECTION for handwriting
    because it performs a deeper layout analysis (pages → blocks → paragraphs
    → words → symbols) which yields better results on irregular letterforms.
    """

    def __init__(self):
        self.client = vision.ImageAnnotatorClient()

    def extract(self, image_path: str, language_hints: list = None) -> dict:
        """
        Extract handwritten text with full structural hierarchy.

        Args:
            image_path:     Path to image containing handwritten text.
            language_hints: List of BCP-47 codes, e.g. ['en', 'fr'].
                            Improves accuracy for mixed-language documents.

        Returns:
            Dictionary with extracted text, page stats, block structure,
            and detected language.

        Raises:
            FileNotFoundError: If the image file does not exist.
            RuntimeError: If the Vision API returns an error.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {image_path}")

        logger.info(f"Running handwriting extraction on: {path.name}")

        with open(image_path, "rb") as f:
            image = vision.Image(content=f.read())

        context = vision.ImageContext(language_hints=language_hints or ["en"])
        response = self.client.document_text_detection(image=image, image_context=context)

        if response.error.message:
            raise RuntimeError(f"Vision API error: {response.error.message}")

        annotation = response.full_text_annotation

        if not annotation.text:
            logger.warning(f"No handwriting detected in: {path.name}")
            return {
                "text": "",
                "pages": [],
                "detected_language": "unknown",
                "confidence": 0.0,
            }

        pages = self._parse_pages(annotation.pages)
        detected_language = self._detect_primary_language(annotation)

        result = {
            "text": annotation.text,
            "pages": pages,
            "page_count": len(pages),
            "detected_language": detected_language,
            "average_confidence": self._average_confidence(pages),
        }

        logger.info(
            f"Extracted {len(annotation.text.split())} words | "
            f"Language: {detected_language}"
        )
        return result

    def extract_words_with_positions(self, image_path: str) -> list:
        """
        Return individual words with their bounding box coordinates.
        Useful for reconstructing handwritten form fields or labelled data.

        Args:
            image_path: Path to the image file.

        Returns:
            List of dicts: {text, confidence, bounding_box, page, block, paragraph}.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {image_path}")

        with open(image_path, "rb") as f:
            image = vision.Image(content=f.read())

        response = self.client.document_text_detection(image=image)

        if response.error.message:
            raise RuntimeError(f"Vision API error: {response.error.message}")

        words = []
        for page_num, page in enumerate(response.full_text_annotation.pages):
            for block_num, block in enumerate(page.blocks):
                for para_num, para in enumerate(block.paragraphs):
                    for word in para.words:
                        word_text = "".join(
                            symbol.text for symbol in word.symbols
                        )
                        words.append(
                            {
                                "text": word_text,
                                "confidence": word.confidence,
                                "bounding_box": [
                                    {"x": v.x, "y": v.y}
                                    for v in word.bounding_box.vertices
                                ],
                                "page": page_num,
                                "block": block_num,
                                "paragraph": para_num,
                            }
                        )
        return words

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_pages(self, pages) -> list:
        result = []
        for page in pages:
            langs = []
            if page.property and page.property.detected_languages:
                langs = [
                    {
                        "code": dl.language_code,
                        "confidence": round(dl.confidence, 4),
                    }
                    for dl in page.property.detected_languages
                ]
            result.append(
                {
                    "width": page.width,
                    "height": page.height,
                    "block_count": len(page.blocks),
                    "confidence": round(page.confidence, 4),
                    "detected_languages": langs,
                }
            )
        return result

    def _detect_primary_language(self, annotation) -> str:
        try:
            langs = annotation.pages[0].property.detected_languages
            if langs:
                return langs[0].language_code
        except (IndexError, AttributeError):
            pass
        return "unknown"

    def _average_confidence(self, pages: list) -> float:
        if not pages:
            return 0.0
        confidences = [p["confidence"] for p in pages if p["confidence"] > 0]
        return round(sum(confidences) / len(confidences), 4) if confidences else 0.0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python handwriting.py <image_path> [lang1,lang2,...]")
        print("  Example: python handwriting.py scan.jpg en,fr")
        sys.exit(1)

    image_path = sys.argv[1]
    langs = sys.argv[2].split(",") if len(sys.argv) > 2 else ["en"]

    extractor = HandwritingExtractor()
    result = extractor.extract(image_path, language_hints=langs)

    print(f"\n--- Extracted Handwriting ---\n{result['text']}")
    print(f"\n--- Metadata ---")
    print(f"Language    : {result['detected_language']}")
    print(f"Confidence  : {result['average_confidence']:.2%}")
    print(f"Pages       : {result['page_count']}")
