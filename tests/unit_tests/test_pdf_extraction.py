"""Unit tests for agent.pdf_extraction, using synthetic in-memory PDFs.

These tests build their own PDFs with PyMuPDF rather than depending on the
external test_pdfs corpus, so they are deterministic and run anywhere the
`pdf` extra is installed.
"""

import io
import shutil

import pytest

fitz = pytest.importorskip(
    "pymupdf", reason="pymupdf not installed; run: pip install -e '.[pdf]'"
)

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from agent.pdf_extraction import extract_pdf_text  # noqa: E402


def _tesseract_available() -> bool:
    if shutil.which("tesseract") is not None:
        return True
    import os

    return bool(os.environ.get("TESSERACT_CMD"))


requires_tesseract = pytest.mark.skipif(
    not _tesseract_available(), reason="Tesseract OCR binary not installed"
)


def _make_pdf(
    pages: list[bytes | None] | None = None,
    rotation: int = 0,
    with_text: str | None = None,
) -> bytes:
    """Build a minimal single- or multi-page PDF for testing.

    If `with_text` is given, inserts real embedded text. If `pages` is
    given, each entry is PNG bytes to embed as a full-page image (or None
    for a blank page).
    """
    doc = fitz.open()
    if with_text is not None:
        page = doc.new_page()
        if rotation:
            page.set_rotation(rotation)
        page.insert_text((72, 72), with_text)
    else:
        for png_bytes in pages or [None]:
            page = doc.new_page(width=850, height=1100)
            if png_bytes is not None:
                page.insert_image(page.rect, stream=png_bytes)
    return doc.tobytes()  # type: ignore[no-any-return]


_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _load_test_font(size: int) -> ImageFont.BaseImageFont:
    """Load a real TrueType font for synthetic OCR pages.

    Tesseract's orientation detection (OSD) needs realistic glyph shapes to
    work reliably; Pillow's built-in bitmap `load_default` font is not
    sufficient at large sizes. Falls back to the bitmap default (with
    reduced OSD reliability) if no TrueType font is found on the system.
    """
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _make_scanned_page_png(rotate_degrees: int = 0) -> bytes:
    """Render a realistic paragraph of English text as a synthetic scanned page.

    OSD orientation detection needs enough real text structure (not just a
    single repeated word) to reliably determine rotation, so this renders
    several distinct sentences rather than one short marker string.
    """
    img = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(img)
    font = _load_test_font(48)
    lines = [
        "SCANNED DOCUMENT PAGE FOR TESTING",
        "This is a synthetic scanned document page used for testing purposes.",
        "It contains several lines of normal English prose so that OCR and",
        "orientation detection have enough real text structure to work with.",
        "The quick brown fox jumps over the lazy dog near the riverbank.",
    ]
    y = 150
    for line in lines:
        draw.text((100, y), line, fill="black", font=font)
        y += 100
    if rotate_degrees:
        img = img.rotate(rotate_degrees, expand=True, fillcolor="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_extract_embedded_text_pdf() -> None:
    pdf_bytes = _make_pdf(with_text="Hello World, this is a real test sentence.")
    result = extract_pdf_text(pdf_bytes)
    assert result.error is None
    assert result.page_count == 1
    assert result.pages[0].method == "embedded_text"
    assert result.pages[0].rotation_applied == 0
    assert "Hello World" in result.text


def test_extract_page_with_rotate_metadata_still_uses_embedded_text() -> None:
    pdf_bytes = _make_pdf(
        with_text="Rotated metadata but real text layer.", rotation=180
    )
    result = extract_pdf_text(pdf_bytes)
    assert result.error is None
    assert result.pages[0].method == "embedded_text"
    assert "Rotated metadata" in result.text


@requires_tesseract
def test_extract_scanned_upright_page_via_ocr() -> None:
    png = _make_scanned_page_png()
    pdf_bytes = _make_pdf(pages=[png])
    result = extract_pdf_text(pdf_bytes)
    assert result.error is None
    assert result.pages[0].method == "ocr"
    assert result.pages[0].rotation_applied == 0
    assert "SCANNED" in result.text.upper()


@requires_tesseract
def test_extract_scanned_upside_down_page_via_ocr() -> None:
    png = _make_scanned_page_png(rotate_degrees=180)
    pdf_bytes = _make_pdf(pages=[png])
    result = extract_pdf_text(pdf_bytes)
    assert result.error is None
    assert result.pages[0].method == "ocr"
    assert result.pages[0].rotation_applied == 180
    assert "SCANNED" in result.text.upper()


@requires_tesseract
def test_extract_90_degree_rotation() -> None:
    png = _make_scanned_page_png(rotate_degrees=90)
    pdf_bytes = _make_pdf(pages=[png])
    result = extract_pdf_text(pdf_bytes)
    assert result.error is None
    assert result.pages[0].method == "ocr"
    assert result.pages[0].rotation_applied in (90, 270)
    assert "SCANNED" in result.text.upper()


def test_extract_blank_page_does_not_crash() -> None:
    # A page with neither embedded text nor an image: falls through to the
    # OCR path on a blank white image. Must not raise, even with near-empty
    # OCR output.
    pdf_bytes = _make_pdf(pages=[None])
    result = extract_pdf_text(pdf_bytes)
    assert result.error is None
    assert result.page_count == 1


def test_extract_corrupted_pdf_bytes() -> None:
    result = extract_pdf_text(b"not a real pdf")
    assert result.error is not None
    assert result.page_count == 0
