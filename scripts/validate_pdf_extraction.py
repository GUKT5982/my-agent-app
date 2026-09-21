"""Batch-validate PDF text extraction against a real corpus of PDF files.

Manual/on-demand tool - NOT part of `make test` or CI. Runs `extract_pdf_text`
directly (no LangGraph runtime involved) against every PDF in a directory,
isolates per-file errors and timeouts, and writes a summary report so you can
see, across a large real-world corpus, how many files failed, how many pages
needed OCR, and how long extraction took.

Usage:
    python scripts/validate_pdf_extraction.py --limit 20
    python scripts/validate_pdf_extraction.py --sample 50 --seed 1
    python scripts/validate_pdf_extraction.py --output report.json --csv report.csv
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Allow running this script directly without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.pdf_extraction import extract_pdf_text  # noqa: E402

DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[1].parent / "test_pdfs"
DEFAULT_TIMEOUT_SECONDS = 120


@dataclass
class FileReport:
    """Validation outcome for a single PDF file."""

    path: str
    size_bytes: int
    page_count: int | None
    chars_extracted: int | None
    ocr_page_count: int | None
    embedded_text_page_count: int | None
    pct_pages_ocr: float | None
    elapsed_seconds: float
    error: str | None


def _extract_worker(path_str: str) -> dict[str, Any]:
    """Run extraction for one file in a worker process; returns a plain dict."""
    data = Path(path_str).read_bytes()
    result = extract_pdf_text(data)
    return {
        "page_count": result.page_count,
        "chars_extracted": len(result.text),
        "ocr_page_count": result.ocr_page_count,
        "embedded_text_page_count": result.embedded_text_page_count,
        "error": result.error,
    }


def _validate_one(
    path: Path, timeout: int, pool: multiprocessing.pool.Pool
) -> FileReport:
    size = path.stat().st_size
    t0 = time.time()
    try:
        outcome = pool.apply_async(_extract_worker, (str(path),)).get(timeout=timeout)
        elapsed = time.time() - t0
        page_count = outcome["page_count"]
        pct_ocr = 100.0 * outcome["ocr_page_count"] / page_count if page_count else None
        return FileReport(
            path=str(path),
            size_bytes=size,
            page_count=page_count,
            chars_extracted=outcome["chars_extracted"],
            ocr_page_count=outcome["ocr_page_count"],
            embedded_text_page_count=outcome["embedded_text_page_count"],
            pct_pages_ocr=pct_ocr,
            elapsed_seconds=elapsed,
            error=outcome["error"],
        )
    except multiprocessing.TimeoutError:
        elapsed = time.time() - t0
        return FileReport(
            path=str(path),
            size_bytes=size,
            page_count=None,
            chars_extracted=None,
            ocr_page_count=None,
            embedded_text_page_count=None,
            pct_pages_ocr=None,
            elapsed_seconds=elapsed,
            error=f"timed out after {timeout}s",
        )
    except Exception as exc:  # noqa: BLE001 - isolate any per-file crash
        elapsed = time.time() - t0
        return FileReport(
            path=str(path),
            size_bytes=size,
            page_count=None,
            chars_extracted=None,
            ocr_page_count=None,
            embedded_text_page_count=None,
            pct_pages_ocr=None,
            elapsed_seconds=elapsed,
            error=f"worker crashed: {exc}",
        )


def _print_summary(reports: list[FileReport]) -> None:
    total = len(reports)
    failures = [r for r in reports if r.error is not None]
    elapsed_values = sorted(r.elapsed_seconds for r in reports)
    ocr_pcts = [r.pct_pages_ocr for r in reports if r.pct_pages_ocr is not None]

    print("\n=== Validation summary ===")
    print(f"Files processed: {total}")
    print(f"Failures: {len(failures)}")
    if elapsed_values:
        median = elapsed_values[len(elapsed_values) // 2]
        avg = sum(elapsed_values) / len(elapsed_values)
        print(
            f"Elapsed seconds - median: {median:.2f}, avg: {avg:.2f}, max: {elapsed_values[-1]:.2f}"
        )
    if ocr_pcts:
        avg_ocr = sum(ocr_pcts) / len(ocr_pcts)
        print(f"Avg % pages requiring OCR (of files with pages): {avg_ocr:.1f}%")
    if failures:
        print("\nFirst failures:")
        for r in failures[:10]:
            print(f"  {r.path}: {r.error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument(
        "--limit", type=int, default=None, help="first N files, sorted (deterministic)"
    )
    parser.add_argument(
        "--sample", type=int, default=None, help="random subset of N files"
    )
    parser.add_argument("--seed", type=int, default=0, help="random seed for --sample")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--output", type=Path, default=Path("scripts/pdf_validation_report.json")
    )
    parser.add_argument(
        "--csv", type=Path, default=None, help="also write a flattened CSV summary"
    )
    args = parser.parse_args()

    if not args.corpus_dir.is_dir():
        print(f"Corpus directory not found: {args.corpus_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted(args.corpus_dir.glob("*.pdf"))
    if args.sample is not None:
        random.seed(args.seed)
        files = random.sample(files, min(args.sample, len(files)))
    elif args.limit is not None:
        files = files[: args.limit]

    print(
        f"Validating {len(files)} file(s) from {args.corpus_dir} (timeout={args.timeout}s/file)"
    )

    reports: list[FileReport] = []
    pool = multiprocessing.Pool(processes=1)
    try:
        for i, path in enumerate(files, start=1):
            report = _validate_one(path, args.timeout, pool)
            reports.append(report)
            print(
                f"[{i}/{len(files)}] {path.name}: error={report.error} time={report.elapsed_seconds:.1f}s"
            )
            if report.error is not None and "timed out" in report.error:
                # The stuck worker can't be reclaimed; replace the pool.
                pool.terminate()
                pool = multiprocessing.Pool(processes=1)
    finally:
        pool.terminate()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps([asdict(r) for r in reports], indent=2))
    print(f"\nWrote JSON report to {args.output}")

    if args.csv:
        import csv

        with args.csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=list(asdict(reports[0]).keys()) if reports else []
            )
            writer.writeheader()
            for r in reports:
                writer.writerow(asdict(r))
        print(f"Wrote CSV report to {args.csv}")

    _print_summary(reports)


if __name__ == "__main__":
    main()
