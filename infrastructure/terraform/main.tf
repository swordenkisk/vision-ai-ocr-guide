terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Uncomment to store state in GCS
  # backend "gcs" {
  #   bucket = "YOUR_TFSTATE_BUCKET"
  #   prefix = "vision-ocr/state"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# Enable required APIs
# ---------------------------------------------------------------------------

resource "google_project_service" "vision_api" {
  service            = "vision.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "storage_api" {
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquery_api" {
  service            = "bigquery.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "run_api" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudfunctions_api" {
  service            = "cloudfunctions.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "documentai_api" {
  service            = "documentai.googleapis.com"
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Service account
# ---------------------------------------------------------------------------

resource "google_service_account" "ocr_service_account" {
  account_id   = "vision-ocr-sa"
  display_name = "Vision OCR Service Account"
  description  = "Service account for the Vision AI OCR pipeline"
}

resource "google_project_iam_member" "vision_user" {
  project = var.project_id
  role    = "roles/vision.user"
  member  = "serviceAccount:${google_service_account.ocr_service_account.email}"
}

resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.ocr_service_account.email}"
}

resource "google_project_iam_member" "bigquery_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.ocr_service_account.email}"
}

# ---------------------------------------------------------------------------
# Cloud Storage buckets
# ---------------------------------------------------------------------------

resource "google_storage_bucket" "documents_input" {
  name                        = "${var.project_id}-ocr-input"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  lifecycle_rule {
    condition { age = 30 }
    action    { type = "Delete" }
  }
}

resource "google_storage_bucket" "documents_output" {
  name                        = "${var.project_id}-ocr-output"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  lifecycle_rule {
    condition { age = 90 }
    action    { type = "SetStorageClass"; storage_class = "NEARLINE" }
  }
}

# ---------------------------------------------------------------------------
# BigQuery dataset
# ---------------------------------------------------------------------------

resource "google_bigquery_dataset" "ocr_warehouse" {
  dataset_id    = "ocr_warehouse"
  friendly_name = "OCR Warehouse"
  description   = "Extracted text and metadata from Vision AI OCR pipeline"
  location      = var.bq_location

  delete_contents_on_destroy = false
}

resource "google_bigquery_table" "ocr_results" {
  dataset_id = google_bigquery_dataset.ocr_warehouse.dataset_id
  table_id   = "results"
  description = "Per-document OCR extraction results"

  time_partitioning {
    type  = "DAY"
    field = "processing_time"
  }

  schema = jsonencode([
    { name = "document_uri",   type = "STRING",    mode = "REQUIRED" },
    { name = "extracted_text", type = "STRING",    mode = "NULLABLE" },
    { name = "confidence",     type = "FLOAT64",   mode = "NULLABLE" },
    { name = "word_count",     type = "INTEGER",   mode = "NULLABLE" },
    { name = "processing_time",type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "language",       type = "STRING",    mode = "NULLABLE" },
    { name = "source_format",  type = "STRING",    mode = "NULLABLE" },
    { name = "page_count",     type = "INTEGER",   mode = "NULLABLE" },
  ])
}
