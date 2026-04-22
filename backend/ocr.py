"""
============================================================
  FORGE MASTER — OCR module
  Single place that knows about Pillow + pytesseract + the
  tesseract binary. Everything else talks to this module via
  three functions:

      capture_region(bbox) -> PIL.Image | None
      ocr_image(img)       -> str
      run_ocr(bboxes)      -> str   # concat "\\n\\n"

  All imports are LAZY: we only try Pillow / pytesseract at
  the first call, so an app started without OCR never pays
  the import cost and never crashes at boot.

  Engine dispatch: by default every call is routed to the
  deep-learning backend in backend/ocr_alt.py (RapidOCR /
  PaddleOCR), which massively outperforms Tesseract on the
  stylised game fonts we work with. Set FORGE_OCR_ENGINE=
  tesseract to force the legacy path.
============================================================
"""

import logging
import os
import shutil
from typing import List, Optional, Sequence, Tuple

from .constants import TESSERACT_PATH

log = logging.getLogger(__name__)

Bbox = Tuple[int, int, int, int]

# Lazy cache. `_available` is tri-state:
#   None  = not yet checked
#   True  = OCR stack ready (modules + binary located)
#   False = OCR unavailable (missing import or binary)
_available: Optional[bool] = None
_Image = None          # PIL.ImageGrab
_pytesseract = None    # pytesseract module


def _init() -> bool:
    """Attempt to import Pillow + pytesseract and locate tesseract.

    Cached: runs its checks the first time only. Returns True on
    success. Logs a warning and returns False on failure.
    """
    global _available, _Image, _pytesseract
    if _available is not None:
        return _available

    try:
        from PIL import ImageGrab as _ImageGrab  # type: ignore
        import pytesseract as _pyt               # type: ignore
    except Exception as e:
        log.warning("OCR disabled: %s", e)
        _available = False
        return False

    # Binary resolution — prefer the hard-coded Windows path, fall back
    # to whatever is in $PATH (Linux/Mac dev boxes, chocolatey, …).
    binary = TESSERACT_PATH if os.path.isfile(TESSERACT_PATH) else shutil.which("tesseract")
    if not binary:
        log.warning("OCR disabled: tesseract binary not found (looked at %r and $PATH)",
                    TESSERACT_PATH)
        _available = False
        return False

    _pyt.pytesseract.tesseract_cmd = binary
    _Image            = _ImageGrab
    _pytesseract      = _pyt
    _available        = True
    log.info("OCR ready — tesseract: %s", binary)
    return True


# ── Engine dispatch ─────────────────────────────────────────
# Default = RapidOCR/PaddleOCR via backend/ocr_alt.py. Set
# FORGE_OCR_ENGINE=tesseract (or empty) to fall back to the
# legacy Tesseract path.
def _alt_engine_requested() -> Optional[str]:
    v = (os.environ.get("FORGE_OCR_ENGINE", "rapid") or "").strip().lower()
    if v in ("rapid", "rapidocr", "paddle", "paddleocr", "alt", "dl"):
        return v
    return None


def _alt_module():
    """Import and return backend.ocr_alt lazily. None on failure."""
    try:
        from . import ocr_alt as _alt  # type: ignore
        return _alt
    except Exception as e:
        log.warning("Alt-OCR module failed to load: %s", e)
        return None


def is_available() -> bool:
    """Public flag: True if capture + OCR will work.

    If FORGE_OCR_ENGINE points to an alt backend, we report its
    availability instead of Tesseract's.
    """
    if _alt_engine_requested():
        alt = _alt_module()
        return bool(alt and alt.is_available())
    return _init()


def capture_region(bbox: Bbox):
    """Grab a rectangular screen region. Returns a PIL.Image, or None."""
    if _alt_engine_requested():
        alt = _alt_module()
        if alt is not None:
            return alt.capture_region(bbox)
        return None
    if not _init():
        return None
    try:
        return _Image.grab(bbox=tuple(bbox))
    except Exception as e:
        log.warning("capture_region(%r) failed: %s", bbox, e)
        return None


def ocr_image(img) -> str:
    """OCR a PIL image. Returns '' on failure or empty input.

    If FORGE_OCR_ENGINE is set to a deep-learning backend (rapidocr or
    paddleocr), the call is forwarded to backend/ocr_alt.py. Otherwise
    the image is passed straight to Tesseract with PSM=6 (uniform block
    of text) and English.
    """
    if _alt_engine_requested():
        alt = _alt_module()
        return alt.ocr_image(img) if alt is not None else ""
    if img is None or not _init():
        return ""
    try:
        return _pytesseract.image_to_string(img, config="--psm 6 -l eng")
    except Exception as e:
        log.warning("ocr_image() failed: %s", e)
        return ""


def run_ocr(bboxes: Sequence[Bbox]) -> str:
    """Capture + OCR each bbox, join results with blank lines.

    Empty / failed bboxes are silently skipped — the caller can detect
    'totally empty output' by checking the return string itself.
    """
    if _alt_engine_requested():
        alt = _alt_module()
        return alt.run_ocr(bboxes) if alt is not None else ""
    if not _init():
        return ""
    out: List[str] = []
    for bbox in bboxes:
        img = capture_region(bbox)
        if img is None:
            continue
        text = ocr_image(img).strip()
        if text:
            out.append(text)
    return "\n\n".join(out)
