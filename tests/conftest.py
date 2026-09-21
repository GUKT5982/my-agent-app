import os
import socket
from pathlib import Path
from urllib.parse import urlparse

import pytest
from dotenv import load_dotenv

# TESSERACT_CMD lives in .env alongside the app's other runtime settings.
# Without loading it here the OCR tests skip themselves on any machine where
# tesseract isn't also on PATH - silently dropping coverage of the OCR and
# orientation-correction paths.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# The langsmith pytest plugin uploads results for every @pytest.mark.langsmith
# test, so without credentials each one fails on a 401 before its body ever
# runs - hiding whether the code under test actually works. Running them
# untracked keeps that coverage.
if not os.environ.get("LANGSMITH_API_KEY"):
    os.environ.setdefault("LANGSMITH_TEST_TRACKING", "false")

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


def _ollama_reachable() -> bool:
    url = urlparse(os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL))
    try:
        with socket.create_connection(
            (url.hostname or "localhost", url.port or 11434), timeout=1
        ):
            return True
    except OSError:
        return False


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requires_ollama: needs a reachable Ollama server to run"
    )


def pytest_collection_modifyitems(config, items):
    """Skip model-backed tests when Ollama isn't running.

    Mirrors how the OCR tests treat a missing Tesseract binary: an absent
    external dependency is reported as a skip with a reason, so a red suite
    always means a real defect.
    """
    if _ollama_reachable():
        return
    skip_ollama = pytest.mark.skip(
        reason=f"Ollama not reachable at "
        f"{os.environ.get('OLLAMA_BASE_URL', DEFAULT_OLLAMA_BASE_URL)}"
    )
    for item in items:
        if "requires_ollama" in item.keywords:
            item.add_marker(skip_ollama)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
