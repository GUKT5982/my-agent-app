"""Integration test: run the real pdf_extractor graph end-to-end for the
quote-to-form auto-fill path (extract_pdf -> extract_quote_fields -> fill_form).

Requires a running Ollama with the configured model, same as test_graph.py.
"""

import base64
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip(
    "pymupdf", reason="pymupdf not installed; run: pip install -e '.[pdf]'"
)

from agent import pdf_graph  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from generate_form_demo import build_form_pdf, build_quote_pdf  # noqa: E402

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        shutil.which("tesseract") is None
        and not __import__("os").environ.get("TESSERACT_CMD"),
        reason="Tesseract OCR binary not installed",
    ),
]


@pytest.mark.langsmith
async def test_quote_to_form_fills_all_fields() -> None:
    quote_b64 = base64.b64encode(build_quote_pdf()).decode("ascii")
    form_b64 = base64.b64encode(build_form_pdf()).decode("ascii")

    res = await pdf_graph.ainvoke(
        {"pdf_base64": quote_b64, "form_template_base64": form_b64}
    )

    assert res["error"] is None
    assert res["extracted_fields"]["error"] is None
    assert res["extracted_fields"]["vendor_name"]
    assert len(res["extracted_fields"]["items"]) == 3
    assert res["fill_warnings"] == []
    assert res["filled_form_base64"]


@pytest.mark.langsmith
async def test_plain_extraction_skips_form_fill_when_no_template() -> None:
    quote_b64 = base64.b64encode(build_quote_pdf()).decode("ascii")

    res = await pdf_graph.ainvoke({"pdf_base64": quote_b64})

    assert res["error"] is None
    assert "extracted_fields" not in res
    assert "filled_form_base64" not in res
