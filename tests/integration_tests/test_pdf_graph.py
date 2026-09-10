"""Integration test: run the real pdf_extractor graph against real files.

Feeds a real file from the sibling `test_pdfs` corpus in as base64-encoded
bytes, exactly the way a real API client would submit an uploaded file
(rather than typing a local path into LangGraph Studio's input box).
"""

import base64
import os
import shutil
from pathlib import Path

import pytest

pytest.importorskip(
    "pymupdf", reason="pymupdf not installed; run: pip install -e '.[pdf]'"
)

from agent import pdf_graph  # noqa: E402

# my-agent-app/tests/integration_tests -> my-agent-app -> agent/ (sibling test_pdfs)
TEST_PDFS_DIR = Path(__file__).resolve().parents[2].parent / "test_pdfs"


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None or bool(
        os.environ.get("TESSERACT_CMD")
    )


pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        not _tesseract_available(),
        reason="Tesseract OCR binary not installed",
    ),
    pytest.mark.skipif(
        not TEST_PDFS_DIR.is_dir(), reason="sibling test_pdfs corpus not present"
    ),
]


@pytest.mark.langsmith
async def test_pdf_graph_extracts_real_file() -> None:
    # Deterministic small files for a fast, reproducible test.
    candidates = sorted(
        (p for p in TEST_PDFS_DIR.glob("*.pdf") if p.stat().st_size < 2_000_000),
        key=lambda p: p.name,
    )[:2]
    assert candidates, "expected at least one small PDF in the test_pdfs corpus"

    for path in candidates:
        pdf_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        res = await pdf_graph.ainvoke({"pdf_base64": pdf_b64})
        assert res["error"] is None, f"{path.name}: {res['error']}"
        assert res["page_count"] >= 0
        assert isinstance(res["text"], str)
