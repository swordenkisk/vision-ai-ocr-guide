variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run, GCS, and Cloud Functions"
  type        = string
  default     = "us-central1"
}

variable "bq_location" {
  description = "BigQuery dataset location (e.g. US, EU, us-central1)"
  type        = string
  default     = "US"
}
