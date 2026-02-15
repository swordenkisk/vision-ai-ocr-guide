"""
layout_analyzer.py - Spatial text mapping and document layout analysis.
Reconstructs the visual structure of a document (columns, tables, sections)
from Vision API bounding-box data.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

from google.cloud import vision

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class BoundingBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @classmethod
    def from_vertices(cls, vertices) -> "BoundingBox":
        xs = [v.x for v in vertices]
        ys = [v.y for v in vertices]
        return cls(x_min=min(xs), y_min=min(ys), x_max=max(xs), y_max=max(ys))

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center_x(self) -> float:
        return (self.x_min + self.x_max) / 2

    @property
    def center_y(self) -> float:
        return (self.y_min + self.y_max) / 2


@dataclass
class TextBlock:
    text: str
    block_type: str
    bounding_box: BoundingBox
    confidence: float
    paragraphs: List[str] = field(default_factory=list)


@dataclass
class DocumentLayout:
    page_width: int
    page_height: int
    blocks: List[TextBlock] = field(default_factory=list)
    reading_order: List[str] = field(default_factory=list)


class LayoutAnalyzer:
    """
    Analyzes the spatial structure of documents extracted via Vision API.

    Capabilities:
    - Block-level layout mapping with type classification
    - Reading-order reconstruction (top-left → bottom-right)
    - Column detection for multi-column documents
    - Table region identification (heuristic)
    """

    BLOCK_TYPE_MAP = {
        0: "UNKNOWN",
        1: "TEXT",
        2: "TABLE",
        3: "PICTURE",
        4: "RULER",
        5: "BARCODE",
    }

    def __init__(self):
        self.client = vision.ImageAnnotatorClient()

    def analyze(self, image_path: str) -> DocumentLayout:
        """
        Perform full layout analysis on a document image.

        Args:
            image_path: Path to the document image.

        Returns:
            DocumentLayout with block structure and reading order.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {image_path}")

        logger.info(f"Analyzing layout of: {path.name}")

        with open(image_path, "rb") as f:
            image = vision.Image(content=f.read())

        response = self.client.document_text_detection(image=image)

        if response.error.message:
            raise RuntimeError(f"Vision API error: {response.error.message}")

        if not response.full_text_annotation.pages:
            logger.warning("No pages found in document.")
            return DocumentLayout(page_width=0, page_height=0)

        page = response.full_text_annotation.pages[0]
        layout = DocumentLayout(
            page_width=page.width,
            page_height=page.height,
        )

        for block in page.blocks:
            text_block = self._parse_block(block)
            layout.blocks.append(text_block)

        layout.blocks = self._sort_reading_order(layout.blocks)
        layout.reading_order = [b.text[:80] for b in layout.blocks if b.text.strip()]

        logger.info(
            f"Found {len(layout.blocks)} block(s) | "
            f"Page: {layout.page_width}x{layout.page_height}px"
        )
        return layout

    def detect_columns(self, layout: DocumentLayout, tolerance: float = 0.1) -> List[List[TextBlock]]:
        """
        Group text blocks into columns using x-axis clustering.

        Args:
            layout:    DocumentLayout from analyze().
            tolerance: Fraction of page width to use as column-merge threshold.

        Returns:
            List of columns, each being a list of TextBlocks sorted top-to-bottom.
        """
        if not layout.blocks:
            return []

        threshold = layout.page_width * tolerance
        text_blocks = [b for b in layout.blocks if b.block_type == "TEXT"]

        # Sort blocks by horizontal center
        text_blocks.sort(key=lambda b: b.bounding_box.center_x)

        columns: List[List[TextBlock]] = []
        for block in text_blocks:
            placed = False
            for col in columns:
                col_center = sum(b.bounding_box.center_x for b in col) / len(col)
                if abs(block.bounding_box.center_x - col_center) <= threshold:
                    col.append(block)
                    placed = True
                    break
            if not placed:
                columns.append([block])

        # Sort each column top-to-bottom
        for col in columns:
            col.sort(key=lambda b: b.bounding_box.y_min)

        return columns

    def find_tables(self, layout: DocumentLayout) -> List[TextBlock]:
        """Return blocks classified as TABLE by the Vision API."""
        return [b for b in layout.blocks if b.block_type == "TABLE"]

    def to_dict(self, layout: DocumentLayout) -> dict:
        """Serialize a DocumentLayout to a plain dictionary."""
        return {
            "page_width": layout.page_width,
            "page_height": layout.page_height,
            "block_count": len(layout.blocks),
            "blocks": [
                {
                    "text": b.text[:200],
                    "block_type": b.block_type,
                    "confidence": b.confidence,
                    "bounding_box": asdict(b.bounding_box),
                }
                for b in layout.blocks
            ],
            "reading_order": layout.reading_order,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_block(self, block) -> TextBlock:
        paragraphs_text = []
        for para in block.paragraphs:
            words = []
            for word in para.words:
                word_text = "".join(s.text for s in word.symbols)
                words.append(word_text)
            paragraphs_text.append(" ".join(words))

        block_text = "\n".join(paragraphs_text)
        bbox = BoundingBox.from_vertices(block.bounding_box.vertices)
        block_type = self.BLOCK_TYPE_MAP.get(block.block_type, "UNKNOWN")

        return TextBlock(
            text=block_text,
            block_type=block_type,
            bounding_box=bbox,
            confidence=round(block.confidence, 4),
            paragraphs=paragraphs_text,
        )

    def _sort_reading_order(self, blocks: List[TextBlock]) -> List[TextBlock]:
        """Sort blocks in Western reading order: top-to-bottom, left-to-right."""
        return sorted(blocks, key=lambda b: (b.bounding_box.y_min, b.bounding_box.x_min))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python layout_analyzer.py <image_path>")
        sys.exit(1)

    analyzer = LayoutAnalyzer()
    layout = analyzer.analyze(sys.argv[1])

    print(f"\nPage dimensions : {layout.page_width} x {layout.page_height} px")
    print(f"Total blocks    : {len(layout.blocks)}")
    print("\n--- Reading Order ---")
    for i, snippet in enumerate(layout.reading_order, 1):
        print(f"  {i:>2}. {snippet}")

    columns = analyzer.detect_columns(layout)
    print(f"\n--- Detected Columns: {len(columns)} ---")
    for i, col in enumerate(columns, 1):
        print(f"  Column {i}: {len(col)} block(s)")
