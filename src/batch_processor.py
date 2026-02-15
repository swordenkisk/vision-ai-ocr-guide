"""
batch_processor.py - High-volume document automation using thread-pool parallelism.
Processes entire directories with error isolation and JSON reporting.
"""

import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from src.ocr import DocumentExtractor, SUPPORTED_FORMATS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    Parallel OCR processor for high-volume document workflows.

    Processes all supported files in an input directory, saves per-file JSON
    results to an output directory, and writes a summary report on completion.

    Usage:
        processor = BatchProcessor(max_workers=10)
        report = processor.process_directory("./documents", "./results")
    """

    def __init__(self, max_workers: int = 10, language: str = "en"):
        """
        Args:
            max_workers: Maximum parallel Vision API threads. Keep ≤ 10 to
                         stay within default quota limits.
            language:    Default BCP-47 language hint for all documents.
        """
        self.extractor = DocumentExtractor()
        self.max_workers = max_workers
        self.language = language

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_directory(self, input_dir: str, output_dir: str) -> dict:
        """
        Process every supported file in input_dir in parallel.

        Args:
            input_dir:  Source directory containing images/PDFs.
            output_dir: Destination directory for JSON results and report.

        Returns:
            Summary dictionary with lists of successful and failed files.
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)

        if not input_path.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        output_path.mkdir(parents=True, exist_ok=True)

        files = [
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS
        ]

        if not files:
            logger.warning(f"No supported files found in: {input_dir}")
            return {"successful": [], "failed": [], "total": 0}

        logger.info(f"Found {len(files)} file(s) to process with {self.max_workers} workers")

        results = {"successful": [], "failed": [], "total": len(files)}
        start_time = datetime.utcnow()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(self._process_single, f): f
                for f in files
            }

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    data = future.result()
                    self._save_result(output_path, file_path, data)
                    results["successful"].append(str(file_path))
                    logger.info(f"✓ {file_path.name}")
                except Exception as exc:
                    error_info = {"file": str(file_path), "error": str(exc)}
                    results["failed"].append(error_info)
                    logger.error(f"✗ {file_path.name}: {exc}")

        results["duration_seconds"] = (datetime.utcnow() - start_time).total_seconds()
        results["success_rate"] = (
            len(results["successful"]) / len(files) * 100 if files else 0
        )

        self._write_report(output_path, results)
        self._print_summary(results)

        return results

    def process_files(self, file_paths: list, output_dir: str) -> dict:
        """
        Process an explicit list of files rather than a full directory.

        Args:
            file_paths: List of file paths (str or Path) to process.
            output_dir: Destination directory for JSON results.

        Returns:
            Summary dictionary with lists of successful and failed files.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results = {"successful": [], "failed": [], "total": len(file_paths)}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(self._process_single, Path(f)): Path(f)
                for f in file_paths
            }

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    data = future.result()
                    self._save_result(output_path, file_path, data)
                    results["successful"].append(str(file_path))
                except Exception as exc:
                    results["failed"].append({"file": str(file_path), "error": str(exc)})

        self._write_report(output_path, results)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_single(self, file_path: Path) -> dict:
        """Invoke the extractor for a single file."""
        return self.extractor.extract(str(file_path), language=self.language)

    def _save_result(self, output_dir: Path, source: Path, data: dict):
        """Write per-file JSON result."""
        output_file = output_dir / f"{source.stem}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _write_report(self, output_dir: Path, results: dict):
        """Write the processing summary report."""
        report_path = output_dir / "_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Report saved: {report_path}")

    def _print_summary(self, results: dict):
        total = results["total"]
        success = len(results["successful"])
        failed = len(results["failed"])
        duration = results.get("duration_seconds", 0)
        rate = results.get("success_rate", 0)

        print("\n" + "=" * 50)
        print("  Batch Processing Summary")
        print("=" * 50)
        print(f"  Total files   : {total}")
        print(f"  Successful    : {success}")
        print(f"  Failed        : {failed}")
        print(f"  Success rate  : {rate:.1f}%")
        print(f"  Duration      : {duration:.2f}s")
        print("=" * 50 + "\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python batch_processor.py <input_dir> <output_dir> [max_workers]")
        print("  Example: python batch_processor.py ./documents ./results 10")
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    max_workers = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    processor = BatchProcessor(max_workers=max_workers)
    processor.process_directory(input_dir, output_dir)
