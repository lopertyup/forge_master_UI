"""
============================================================
  FORGE MASTER — Alternative OCR engine (RapidOCR / PaddleOCR)
  Drop-in replacement for backend/ocr.py using a deep-learning
  engine instead of Tesseract.

  Why: deep-learning OCR models (PaddleOCR family) massively
  outperform Tesseract on stylised game fonts, small text, and
  the kind of sign / decimal glitches we keep hitting.

  Two backends supported, auto-selected:
    1. rapidocr_onnxruntime   (recommended: ~20 MB, pure CPU,
                               same model as PaddleOCR)
    2. paddleocr              (fallback: heavier, pulls paddle
                               framework, same accuracy)

  Install one of:
    pip install rapidocr_onnxruntime pillow
    pip install paddleocr paddlepaddle pillow

  Public API — identical to backend/ocr.py so callers don't
  have to care which backend is active:

      is_available() -> bool
      capture_region(bbox) -> PIL.Image | None
      ocr_image(img) -> str
      run_ocr(bboxes) -> str   # "\\n\\n"-joined
============================================================
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

Bbox = Tuple[int, int, int, int]

# Lazy cache, same shape as backend/ocr.py
_available:   Optional[bool] = None
_ImageGrab               = None     # PIL.ImageGrab
_PIL_Image               = None     # PIL.Image
_engine_name: Optional[str] = None  # "rapidocr" | "paddleocr"
_engine:                  object = None  # the instantiated engine


def _init() -> bool:
    """Locate an available DL-OCR backend and initialise it.

    Tries rapidocr_onnxruntime first (cheap), then paddleocr.
    Both are imported lazily so a boot without DL deps costs nothing.
    """
    global _available, _ImageGrab, _PIL_Image, _engine, _engine_name
    if _available is not None:
        return _available

    # PIL is required for screen capture either way.
    try:
        from PIL import ImageGrab as _IG
        from PIL import Image as _Im
    except Exception as e:
        log.warning("Alt-OCR disabled: Pillow missing (%s)", e)
        _available = False
        return False

    # --- Backend #1: rapidocr_onnxruntime (preferred) ---
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
        _engine = RapidOCR()
        _engine_name = "rapidocr"
        _ImageGrab = _IG
        _PIL_Image = _Im
        _available = True
        log.info("Alt-OCR ready — engine: rapidocr_onnxruntime")
        return True
    except Exception as e:
        log.debug("rapidocr_onnxruntime unavailable: %s", e)

    # --- Backend #2: paddleocr ---
    try:
        from paddleocr import PaddleOCR  # type: ignore
        _engine = PaddleOCR(use_angle_cls=False, lang="en",
                            show_log=False)
        _engine_name = "paddleocr"
        _ImageGrab = _IG
        _PIL_Image = _Im
        _available = True
        log.info("Alt-OCR ready — engine: paddleocr")
        return True
    except Exception as e:
        log.debug("paddleocr unavailable: %s", e)

    log.warning(
        "Alt-OCR disabled: install `rapidocr_onnxruntime` "
        "(recommended) or `paddleocr paddlepaddle` to enable it.")
    _available = False
    return False


def is_available() -> bool:
    return _init()


def engine_name() -> Optional[str]:
    """Return the name of the selected backend, or None."""
    _init()
    return _engine_name


def capture_region(bbox: Bbox):
    """Grab a screen region — same semantics as backend/ocr.py."""
    if not _init():
        return None
    try:
        return _ImageGrab.grab(bbox=tuple(bbox))
    except Exception as e:
        log.warning("capture_region(%r) failed: %s", bbox, e)
        return None


def _to_numpy(img):
    """Convert a PIL image to an RGB numpy array (both engines want np).

    Imported lazily so numpy is only required at the first call.
    """
    import numpy as np  # local import
    return np.array(img.convert("RGB"))


def _lines_from_rapidocr(result) -> List[str]:
    # RapidOCR returns (result, elapsed). result is list of
    # [box, text, confidence] triples, roughly top-to-bottom already.
    if not result:
        return []
    out = []
    data = result[0] if isinstance(result, tuple) else result
    for item in data or []:
        if len(item) >= 2:
            text = str(item[1]).strip()
            if text:
                out.append(text)
    return out


def _lines_from_paddleocr(result) -> List[str]:
    # PaddleOCR returns [[box, (text, conf)], ...] wrapped in an outer
    # list (one entry per image).
    if not result:
        return []
    out = []
    inner = result[0] if result and isinstance(result[0], list) else result
    for item in inner or []:
        try:
            text = item[1][0].strip()
        except Exception:
            continue
        if text:
            out.append(text)
    return out


def ocr_image(img) -> str:
    """OCR a PIL image via the selected backend.

    Returns a `\\n`-joined string, one line per detected text box,
    top-to-bottom as returned by the engine.
    """
    if img is None or not _init():
        return ""
    try:
        arr = _to_numpy(img)
        if _engine_name == "rapidocr":
            result, _elapsed = _engine(arr)   # type: ignore[misc]
            lines = _lines_from_rapidocr(result)
        elif _engine_name == "paddleocr":
            result = _engine.ocr(arr, cls=False)  # type: ignore[attr-defined]
            lines = _lines_from_paddleocr(result)
        else:
            return ""
        return "\n".join(lines)
    except Exception as e:
        log.warning("ocr_image() failed (%s): %s", _engine_name, e)
        return ""


def run_ocr(bboxes: Sequence[Bbox]) -> str:
    """Capture + OCR each bbox, join with blank lines."""
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
