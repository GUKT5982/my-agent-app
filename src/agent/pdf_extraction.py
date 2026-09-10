"""Extract normalized, readable text from arbitrary PDF files.

Handles both "born-digital" PDFs (with a usable embedded text layer) and
scanned/image-only PDFs. Scanned pages are rasterized and run through
Tesseract OCR; before OCR, each page's orientation is detected and corrected
so that upside-down or sideways scans are read correctly, regardless of
whether the PDF's own page-rotation metadata reflects that.

This module has no dependency on LangGraph — it is plain, synchronous,
framework-agnostic logic so it can be unit-tested and reused (e.g. by the
batch validation script) independently of the graph that wraps it.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field

import pymupdf
import pytesseract  # type: ignore[import-untyped]
from PIL import Image

# Minimum characters an embedded text layer must contain to be trusted
# instead of falling back to OCR. Pages below this are treated as scanned.
DEFAULT_MIN_CHARS_PER_PAGE = 20

# Minimum fraction of alphanumeric characters an embedded text layer must
# have to be trusted. Guards against garbled/mis-encoded text layers that
# technically contain characters but are not readable text.
DEFAULT_MIN_ALPHA_RATIO = 0.5

# Minimum Tesseract orientation-detection confidence required before a
# 90/180/270-degree rotation correction is applied. Below this, the page is
# left as rendered and a warning is recorded instead of guessing.
DEFAULT_MIN_OSD_CONFIDENCE = 1.0

# Render zoom factor for rasterizing scanned pages before OCR (2.0 is
# roughly 144 DPI given PyMuPDF's 72-DPI page space) - a balance between OCR
# accuracy and memory/time cost per page.
DEFAULT_ZOOM = 2.0


@dataclass
class PageResult:
    """Extraction outcome for a single PDF page."""

    page_number: int
    method: str  # "embedded_text" | "ocr"
    rotation_applied: int  # degrees corrected: 0, 90, 180, or 270
    osd_confidence: float | None
    deskew_angle: float | None
    char_count: int
    text: str
    warning: str | None = None


@dataclass
class ExtractionResult:
    """Extraction outcome for a whole PDF document."""

    text: str = ""
    pages: list[PageResult] = field(default_factory=list)
    page_count: int = 0
    ocr_page_count: int = 0
    embedded_text_page_count: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def extract_pdf_text(
    pdf_bytes: bytes,
    *,
    lang: str = "eng",
    zoom: float = DEFAULT_ZOOM,
    min_chars_per_page: int = DEFAULT_MIN_CHARS_PER_PAGE,
    min_alpha_ratio: float = DEFAULT_MIN_ALPHA_RATIO,
    min_osd_confidence: float = DEFAULT_MIN_OSD_CONFIDENCE,
    enable_deskew: bool = True,
    max_pages: int | None = None,
    tesseract_cmd: str | None = None,
) -> ExtractionResult:
    """Extract normalized text from a PDF, using OCR for scanned pages.

    Never raises for malformed input: document-level failures (bad bytes,
    password-protected files) are reported via ``ExtractionResult.error``,
    and page-level failures (OCR orientation detection failing on a sparse
    page, deskew being skipped) are reported as warnings, so callers always
    get a usable result.

    Args:
        pdf_bytes: Raw bytes of the PDF file.
        lang: Tesseract language code(s) to use for OCR.
        zoom: Render zoom factor used when rasterizing scanned pages.
        min_chars_per_page: Minimum embedded-text length to trust it over OCR.
        min_alpha_ratio: Minimum alphanumeric ratio to trust embedded text.
        min_osd_confidence: Minimum OSD confidence to apply a rotation fix.
        enable_deskew: Whether to attempt fine-angle deskewing after coarse
            90/180/270 rotation correction.
        max_pages: If set, stop after this many pages (for quick sampling).
        tesseract_cmd: Explicit path to the tesseract executable. Falls back
            to the ``TESSERACT_CMD`` environment variable, then to whatever
            is on PATH.

    Returns:
        An ExtractionResult with the combined text and per-page detail.
    """
    resolved_cmd = tesseract_cmd or os.environ.get("TESSERACT_CMD")
    if resolved_cmd:
        pytesseract.pytesseract.tesseract_cmd = resolved_cmd

    doc = _open_document(pdf_bytes)
    if doc is None:
        return ExtractionResult(error="Could not open file: not a valid PDF")
    if doc.needs_pass:
        return ExtractionResult(error="PDF is password-protected")

    result = ExtractionResult()
    if doc.page_count == 0:
        result.warnings.append(
            "PDF opened successfully but reports zero pages "
            "(possibly a malformed page tree)"
        )
    text_parts: list[str] = []
    for i in range(doc.page_count):
        if max_pages is not None and i >= max_pages:
            break
        page: pymupdf.Page = doc[i]
        page_result = _extract_page(
            page,
            page_number=i + 1,
            lang=lang,
            zoom=zoom,
            min_chars_per_page=min_chars_per_page,
            min_alpha_ratio=min_alpha_ratio,
            min_osd_confidence=min_osd_confidence,
            enable_deskew=enable_deskew,
        )
        result.pages.append(page_result)
        text_parts.append(f"--- page {page_result.page_number} ---\n{page_result.text}")
        if page_result.method == "ocr":
            result.ocr_page_count += 1
        else:
            result.embedded_text_page_count += 1
        if page_result.warning:
            result.warnings.append(
                f"page {page_result.page_number}: {page_result.warning}"
            )

    result.page_count = len(result.pages)
    result.text = "\n\n".join(text_parts)
    return result


def _open_document(pdf_bytes: bytes) -> pymupdf.Document | None:
    """Open a PDF from bytes, returning None (never raising) on failure."""
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[no-untyped-call]
    except Exception:
        return None
    if doc.page_count == 0 and len(pdf_bytes) == 0:
        return None
    return doc


def _extract_page(
    page: pymupdf.Page,
    *,
    page_number: int,
    lang: str,
    zoom: float,
    min_chars_per_page: int,
    min_alpha_ratio: float,
    min_osd_confidence: float,
    enable_deskew: bool,
) -> PageResult:
    """Extract text from a single page, falling back to OCR if needed."""
    usable, raw_text = _page_has_usable_text(page, min_chars_per_page, min_alpha_ratio)
    if usable:
        return PageResult(
            page_number=page_number,
            method="embedded_text",
            rotation_applied=0,
            osd_confidence=None,
            deskew_angle=None,
            char_count=len(raw_text),
            text=raw_text,
        )

    image = _render_page_to_image(page, zoom)
    image, rotation, osd_confidence, warning = _detect_and_fix_orientation(
        image, min_osd_confidence
    )
    deskew_angle: float | None = None
    if enable_deskew:
        image, deskew_angle = _deskew_fine(image)
    try:
        text = pytesseract.image_to_string(image, lang=lang)
    except pytesseract.pytesseract.TesseractNotFoundError:
        return PageResult(
            page_number=page_number,
            method="ocr",
            rotation_applied=rotation,
            osd_confidence=osd_confidence,
            deskew_angle=deskew_angle,
            char_count=0,
            text="",
            warning="Tesseract OCR engine not found on PATH; install it and/or "
            "set TESSERACT_CMD (see SETUP.txt)",
        )
    except Exception as exc:  # noqa: BLE001 - OCR must never crash the pipeline
        return PageResult(
            page_number=page_number,
            method="ocr",
            rotation_applied=rotation,
            osd_confidence=osd_confidence,
            deskew_angle=deskew_angle,
            char_count=0,
            text="",
            warning=f"OCR failed: {exc}",
        )

    return PageResult(
        page_number=page_number,
        method="ocr",
        rotation_applied=rotation,
        osd_confidence=osd_confidence,
        deskew_angle=deskew_angle,
        char_count=len(text),
        text=text,
        warning=warning,
    )


def _page_has_usable_text(
    page: pymupdf.Page, min_chars_per_page: int, min_alpha_ratio: float
) -> tuple[bool, str]:
    """Decide whether a page's embedded text layer is usable as-is.

    Returns (True, text) when the embedded text layer is long enough and
    contains enough alphanumeric characters to trust; (False, "") when the
    page should instead be rasterized and OCR'd.
    """
    raw = page.get_text("text")  # type: ignore[no-untyped-call]
    stripped = raw.strip()
    if len(stripped) < min_chars_per_page:
        return False, ""
    alnum_count = sum(1 for c in stripped if c.isalnum())
    alnum_ratio = alnum_count / len(stripped)
    if alnum_ratio < min_alpha_ratio:
        return False, ""
    return True, raw


def _render_page_to_image(page: pymupdf.Page, zoom: float) -> Image.Image:
    """Rasterize a PDF page to a Pillow image, honoring page rotation metadata."""
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))  # type: ignore[no-untyped-call]
    return Image.open(io.BytesIO(pix.tobytes("png")))  # type: ignore[no-untyped-call]


def _detect_and_fix_orientation(
    image: Image.Image, min_osd_confidence: float
) -> tuple[Image.Image, int, float | None, str | None]:
    """Detect and correct 90/180/270-degree misorientation via Tesseract OSD.

    Returns (corrected_image, rotation_applied_degrees, osd_confidence, warning).
    Never raises: OSD frequently fails on sparse/blank pages, in which case
    the original image is returned unrotated with a warning.
    """
    try:
        osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
        rotate = int(osd["rotate"])
        confidence = float(osd["orientation_conf"])
    except Exception as exc:  # noqa: BLE001 - OSD failure must not crash extraction
        return image, 0, None, f"orientation detection failed: {exc}, rotation skipped"

    if confidence < min_osd_confidence or rotate == 0:
        warning = (
            None if rotate == 0 else "OSD confidence below threshold, rotation skipped"
        )
        return image, 0, confidence, warning

    # Tesseract's OSD "rotate" is the clockwise angle needed to make the
    # image upright; PIL's Image.rotate() turns counter-clockwise for
    # positive angles, so the correction is the negation.
    corrected = image.rotate(-rotate, expand=True, fillcolor="white")
    return corrected, rotate, confidence, None


def _deskew_fine(image: Image.Image) -> tuple[Image.Image, float | None]:
    """Best-effort fine-angle deskew (a few degrees of scan tilt).

    Applied only after coarse 90/180/270 correction. Entirely optional and
    fail-safe: any error (including OpenCV not being installed) simply
    skips deskewing rather than affecting the OCR result.
    """
    try:
        import cv2  # noqa: PLC0415 - optional dependency, imported lazily
        import numpy as np

        gray = np.array(image.convert("L"))
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
        coords = cv2.findNonZero(thresh)
        if coords is None:
            return image, None
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if not (0.5 < abs(angle) < 15):
            return image, None
        return image.rotate(angle, expand=True, fillcolor="white"), angle
    except Exception:  # noqa: BLE001 - deskew is best-effort only
        return image, None
