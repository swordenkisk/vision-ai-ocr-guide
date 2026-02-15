output "service_account_email" {
  description = "Email of the Vision OCR service account"
  value       = google_service_account.ocr_service_account.email
}

output "input_bucket" {
  description = "GCS bucket for document uploads"
  value       = google_storage_bucket.documents_input.name
}

output "output_bucket" {
  description = "GCS bucket for OCR results"
  value       = google_storage_bucket.documents_output.name
}

output "bigquery_table" {
  description = "Fully qualified BigQuery table ID"
  value       = "${google_bigquery_dataset.ocr_warehouse.dataset_id}.${google_bigquery_table.ocr_results.table_id}"
}
