# Document Format Specifications

Detailed guidance on supported input formats, quality requirements, and
pre-processing recommendations for optimal OCR accuracy.

---

## Supported Input Formats

| Format   | Extension(s)     | Multi-page | Max Size | Notes                              |
|----------|------------------|------------|----------|------------------------------------|
| JPEG     | `.jpg`, `.jpeg`  | No         | 20 MB    | Best for photographs               |
| PNG      | `.png`           | No         | 20 MB    | Lossless; ideal for scanned docs   |
| GIF      | `.gif`           | No         | 20 MB    | Only first frame is processed      |
| BMP      | `.bmp`           | No         | 20 MB    | Uncompressed; large file sizes     |
| WebP     | `.webp`          | No         | 20 MB    | Modern web format                  |
| TIFF     | `.tiff`, `.tif`  | **Yes**    | 20 MB    | Professional scanning standard     |
| PDF      | `.pdf`           | **Yes**    | 20 MB    | All pages processed automatically  |

> Files exceeding 20 MB are automatically downscaled by the Vision API,
> but accuracy may decrease. Pre-scale large files before submission.

---

## Image Quality Guidelines

### Resolution (DPI)

| Use Case                          | Minimum DPI | Recommended DPI |
|-----------------------------------|-------------|-----------------|
| Standard printed text (≥10pt)     | 200         | 300             |
| Small printed text (8–10pt)       | 300         | 400             |
| Very small text (<8pt)            | 400         | 600             |
| Handwritten text                  | 300         | 400             |
| Table / form extraction           | 300         | 300             |

### Image Conditions

**Lighting**
- Avoid harsh shadows across text
- Even, diffused lighting gives best results
- Avoid glare from shiny paper or lamination

**Orientation**
- Text should be upright (0°); Vision API tolerates up to ±5° skew
- Use `document_text_detection` for pages with mixed orientations
- Pre-rotate pages with `Pillow` or `pdf2image` if needed

**Noise and Artifacts**
- Avoid JPEG compression artefacts — use PNG for scanned documents
- Remove heavy halftone patterns from newspaper or magazine scans
- Binarise (convert to pure black/white) for degraded historical documents

---

## Multi-Page Document Handling

### TIFF
Multi-page TIFF files are processed as a single API call. All pages are
returned in sequence in the `full_text_annotation`.

### PDF
PDF files up to 20 MB and up to 2,000 pages are fully supported.
For very large PDFs:
1. Split into chunks of ≤ 20 MB using `PyMuPDF` or `pypdf`
2. Process chunks in parallel with `BatchProcessor`
3. Merge results in order

```python
import fitz  # PyMuPDF

def split_pdf(input_path: str, max_pages: int = 50) -> list:
    doc = fitz.open(input_path)
    chunks = []
    for start in range(0, len(doc), max_pages):
        chunk = fitz.open()
        chunk.insert_pdf(doc, from_page=start, to_page=min(start + max_pages - 1, len(doc) - 1))
        out_path = f"{input_path}_chunk_{start}.pdf"
        chunk.save(out_path)
        chunks.append(out_path)
    return chunks
```

---

## Pre-Processing Recommendations

### Deskewing

```python
from PIL import Image
import numpy as np

def deskew(image_path: str, output_path: str):
    """Simple deskew using Pillow rotation."""
    img = Image.open(image_path).convert("L")
    # Use pytesseract OSD or a custom Hough-line approach for angle detection
    img.save(output_path)
```

### Binarisation (Otsu Threshold)

```python
import cv2

def binarise(image_path: str, output_path: str):
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cv2.imwrite(output_path, binary)
```

### Upscaling Low-Resolution Images

```python
from PIL import Image

def upscale(image_path: str, output_path: str, target_dpi: int = 300):
    img = Image.open(image_path)
    current_dpi = img.info.get("dpi", (72, 72))[0]
    scale = target_dpi / current_dpi
    new_size = (int(img.width * scale), int(img.height * scale))
    upscaled = img.resize(new_size, Image.LANCZOS)
    upscaled.save(output_path, dpi=(target_dpi, target_dpi))
```

---

## Language Hints

Providing the correct language hint can significantly improve accuracy for
non-Latin scripts and mixed-language documents.

```python
context = vision.ImageContext(
    language_hints=["en", "ar", "zh-Hans"],  # Priority order
)
```

Common BCP-47 codes:

| Language           | Code     |
|--------------------|----------|
| English            | `en`     |
| French             | `fr`     |
| German             | `de`     |
| Spanish            | `es`     |
| Arabic             | `ar`     |
| Chinese (Simplified) | `zh-Hans` |
| Chinese (Traditional) | `zh-Hant` |
| Japanese           | `ja`     |
| Korean             | `ko`     |
| Hindi              | `hi`     |

Full list: https://cloud.google.com/vision/docs/languages
