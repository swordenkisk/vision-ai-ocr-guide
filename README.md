# Google Cloud Vision AI OCR

A production-ready toolkit for document digitisation using Google Cloud Vision API,
featuring multi-format support, batch processing, and enterprise deployment patterns.

---

## Quick Start

```bash
# Clone and configure
git clone https://github.com/swordenkisk/vision-ai-ocr-guide.git
cd vision-ai-ocr-guide

# Install dependencies
pip install -r requirements.txt

# Authenticate with Google Cloud
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Run first extraction
python src/ocr.py samples/invoice.jpg
```

---

## Repository Structure

```
vision-ai-ocr-guide/
├── src/
│   ├── ocr.py                 # Core extraction engine
│   ├── batch_processor.py     # High-volume parallel automation
│   ├── handwriting.py         # Cursive & printed handwriting recognition
│   └── layout_analyzer.py     # Spatial text mapping & column detection
├── integrations/
│   ├── gcs_loader.py          # Cloud Storage connector & Cloud Function trigger
│   ├── bigquery_export.py     # Data warehouse streaming pipeline
│   └── document_ai_bridge.py  # Advanced form & invoice parsing
├── infrastructure/
│   ├── Dockerfile             # Container specification
│   ├── docker-compose.yml     # Multi-service orchestration
│   ├── cloudbuild.yaml        # CI/CD → Cloud Run deployment
│   └── terraform/             # GCP resource provisioning (IaC)
├── notebooks/
│   └── interactive_tutorial.ipynb  # Step-by-step exploration
├── docs/
│   ├── format_specifications.md    # Supported formats & quality guidelines
│   └── pricing_optimization.md    # Cost reduction strategies
├── samples/                   # Place test images here
└── requirements.txt
```

---

## Features

- **Single & batch document processing** — process one image or thousands in parallel
- **50+ language support** including handwriting recognition
- **Multi-format input** — JPEG, PNG, TIFF, PDF, BMP, WebP, GIF
- **Spatial layout analysis** — column detection, reading-order reconstruction, table identification
- **GCS integration** — trigger OCR automatically on file upload via Cloud Functions
- **BigQuery export** — stream results to a data warehouse for analytics
- **Document AI bridge** — structured extraction for invoices, forms, and receipts
- **Dockerised microservices** — production-ready container with Cloud Run support
- **Terraform IaC** — one-command GCP infrastructure provisioning

---

## Module Reference

### `src/ocr.py` — Core Extraction Engine

```python
from src.ocr import DocumentExtractor

extractor = DocumentExtractor()

# Standard OCR (photos, sparse layouts)
result = extractor.extract("invoice.jpg", language="en")
print(result["text"])
print(result["word_count"])

# Document OCR (dense text, forms, invoices)
result = extractor.extract_document("report.pdf", language="en")
print(result["pages"])
```

### `src/batch_processor.py` — Parallel Batch Processing

```python
from src.batch_processor import BatchProcessor

processor = BatchProcessor(max_workers=10)
report = processor.process_directory("./documents", "./results")
# Results: per-file JSON + _report.json summary
```

### `src/handwriting.py` — Handwriting Recognition

```python
from src.handwriting import HandwritingExtractor

extractor = HandwritingExtractor()
result = extractor.extract("scan.jpg", language_hints=["en", "fr"])
print(result["text"])
print(result["detected_language"])
```

### `src/layout_analyzer.py` — Spatial Layout Analysis

```python
from src.layout_analyzer import LayoutAnalyzer

analyzer = LayoutAnalyzer()
layout = analyzer.analyze("page.jpg")
columns = analyzer.detect_columns(layout)
tables = analyzer.find_tables(layout)
```

---

## Deployment

### Docker

```bash
docker build -t vision-ocr:latest -f infrastructure/Dockerfile .
docker run \
  -v $(pwd)/documents:/input \
  -v $(pwd)/results:/output \
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/key.json \
  -v $GOOGLE_APPLICATION_CREDENTIALS:/secrets/key.json:ro \
  vision-ocr:latest
```

### Cloud Run (via Cloud Build)

```bash
gcloud builds submit --config infrastructure/cloudbuild.yaml .
```

### Terraform (GCP Infrastructure)

```bash
cd infrastructure/terraform
terraform init
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

---

## Security

- Never commit service account keys — use Secret Manager in production
- Process EU documents in `europe-west` regions for GDPR compliance
- Vision API encrypts data in transit and at rest by default
- Enable VPC Service Controls for sensitive document processing

---

## Requirements

- Python 3.11+
- Google Cloud project with Vision API enabled
- Service account with `roles/vision.user` IAM binding

---

## License

MIT — commercial and non-commercial use permitted.

---

*Last updated: February 2026*
