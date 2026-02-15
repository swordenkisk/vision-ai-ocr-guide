# Pricing Optimisation Guide

Strategies for minimising Google Cloud Vision API costs without sacrificing
accuracy in production OCR workloads.

---

## Vision API Pricing (as of early 2026)

| Feature                    | First 1,000/month | 1,001–5,000,000/month | 5,000,001+/month |
|----------------------------|-------------------|-----------------------|------------------|
| TEXT_DETECTION             | Free              | $1.50 / 1,000         | $0.60 / 1,000    |
| DOCUMENT_TEXT_DETECTION    | Free              | $1.50 / 1,000         | $0.60 / 1,000    |

> Pricing is per-image unit. Each PDF page counts as one unit.
> Always verify current pricing at: https://cloud.google.com/vision/pricing

---

## Optimisation Strategy 1: Batch API Requests

Use `BatchAnnotateImages` to group up to 16 images per API call.
This reduces per-request overhead (network round-trips) without changing
the per-image cost.

```python
from google.cloud import vision

def batch_annotate(image_paths: list) -> list:
    client = vision.ImageAnnotatorClient()

    requests = []
    for path in image_paths:
        with open(path, "rb") as f:
            image = vision.Image(content=f.read())
        requests.append(
            vision.AnnotateImageRequest(
                image=image,
                features=[vision.Feature(type_=vision.Feature.Type.TEXT_DETECTION)],
            )
        )

    # Up to 16 images per call
    response = client.batch_annotate_images(requests=requests)
    return [r.text_annotations for r in response.responses]
```

---

## Optimisation Strategy 2: Choose the Right Detection Method

| Scenario                         | Recommended Method           | Why                              |
|----------------------------------|------------------------------|----------------------------------|
| Printed text, sparse layout      | `text_detection`             | Faster, lower latency            |
| Dense documents, forms, invoices | `document_text_detection`    | Better structural accuracy       |
| Handwriting                      | `document_text_detection`    | Handles irregular letterforms    |
| Single-line labels or barcodes   | `text_detection`             | Overkill to run full layout pass |

---

## Optimisation Strategy 3: Pre-Filter Non-Text Images

Skip the Vision API for images that are unlikely to contain text:

```python
from PIL import Image
import numpy as np

def has_text_likelihood(image_path: str, threshold: float = 0.05) -> bool:
    """
    Heuristic: images with very low contrast variance are likely blank or
    photographic and unlikely to contain OCR-worthy text.
    """
    img = Image.open(image_path).convert("L")
    arr = np.array(img)
    variance = arr.std()
    return variance > (threshold * 255)
```

---

## Optimisation Strategy 4: Cache Results

Avoid re-processing identical documents by hashing their content:

```python
import hashlib
import json
from pathlib import Path

CACHE_DIR = Path(".ocr_cache")
CACHE_DIR.mkdir(exist_ok=True)

def cached_extract(extractor, file_path: str) -> dict:
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()[:16]

    cache_file = CACHE_DIR / f"{file_hash}.json"

    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    result = extractor.extract(file_path)

    with open(cache_file, "w") as f:
        json.dump(result, f)

    return result
```

---

## Optimisation Strategy 5: Regional Endpoints

Route requests to the closest regional endpoint to reduce latency and,
in some configurations, egress costs:

| Region          | Endpoint                                      |
|-----------------|-----------------------------------------------|
| Global          | `vision.googleapis.com`                       |
| United States   | `us-vision.googleapis.com`                    |
| European Union  | `eu-vision.googleapis.com`                    |

```python
from google.api_core.client_options import ClientOptions
from google.cloud import vision

client = vision.ImageAnnotatorClient(
    client_options=ClientOptions(api_endpoint="eu-vision.googleapis.com")
)
```

---

## Optimisation Strategy 6: Image Size Reduction

The Vision API downscales images above its internal threshold, but charges
for the original input bytes transferred. Pre-scale before submitting:

```python
from PIL import Image

def optimise_for_ocr(input_path: str, output_path: str, max_dimension: int = 3000):
    img = Image.open(input_path)
    if max(img.size) > max_dimension:
        ratio = max_dimension / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    # Save as PNG (lossless) to avoid compression artefacts
    img.save(output_path, format="PNG", optimize=True)
```

---

## Monthly Cost Estimation

```python
def estimate_monthly_cost(
    images_per_month: int,
    tier1_limit: int = 1000,
    tier2_limit: int = 5_000_000,
    tier1_price: float = 1.50,
    tier2_price: float = 0.60,
) -> float:
    """Estimate monthly Vision API spend."""
    if images_per_month <= tier1_limit:
        return 0.0
    elif images_per_month <= tier2_limit:
        billable = images_per_month - tier1_limit
        return (billable / 1000) * tier1_price
    else:
        tier1_cost = ((tier2_limit - tier1_limit) / 1000) * tier1_price
        tier2_billable = images_per_month - tier2_limit
        tier2_cost = (tier2_billable / 1000) * tier2_price
        return tier1_cost + tier2_cost


# Examples
print(f"10,000 images/month  : ${estimate_monthly_cost(10_000):.2f}")
print(f"100,000 images/month : ${estimate_monthly_cost(100_000):.2f}")
print(f"1M images/month      : ${estimate_monthly_cost(1_000_000):.2f}")
```

---

## Budget Alerts

Set up GCP budget alerts to avoid surprise bills:

```bash
gcloud billing budgets create \
  --billing-account=YOUR_BILLING_ACCOUNT \
  --display-name="Vision OCR Budget" \
  --budget-amount=500USD \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90 \
  --threshold-rule=percent=100
```
