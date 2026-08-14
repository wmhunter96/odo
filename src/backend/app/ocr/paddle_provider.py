"""Local, free, CPU-capable OCR via PaddleOCR's PP-OCRv6 pipeline.

Unlike Tesseract (a single detect+recognize pass over a page-layout hint
you have to supply), PaddleOCR's unified `PaddleOCR` pipeline bundles
several models behind one call:

    document orientation classify -> document unwarping -> text detection
    -> text-line orientation -> text recognition

The three "use_*" flags below turn on the first, second, and fourth of
those. Text detection/recognition (PP-OCRv6) always run. All of this is
local inference (CPU here; no GPU required) against model weights baked
into the Docker image at build time -- see the Dockerfile -- so there's
no network access, no per-request cost, and no cloud OCR involved, same as
the Tesseract provider this replaces.

Detection is quad (not axis-aligned-box) based and each detected line is
individually cropped and perspective-corrected before recognition, which
is why this needs far less hand-rolled preprocessing than Tesseract did
(see ocr/preprocess.py) -- skewed paper and moderately uneven lighting are
handled by the model pipeline itself rather than by pixel-level tricks
tuned against one specific engine's weaknesses.
"""
from __future__ import annotations

import threading
from typing import Any

import numpy as np
from PIL import Image

from .provider import OCRProvider, OCRResult, OCRWord

_engine_lock = threading.Lock()
_engine: Any = None


def _get_engine() -> Any:
    """Lazily construct and cache the PaddleOCR pipeline.

    Building it loads every sub-model's weights onto CPU, which is slow
    (multiple seconds) and memory-heavy -- worth doing once per process on
    first use, not once per photo. Guarded by a lock since FastAPI can
    have more than one request in flight even with a single worker
    process.
    """
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from paddleocr import PaddleOCR

                _engine = PaddleOCR(
                    lang="en",
                    ocr_version="PP-OCRv6",
                    use_doc_orientation_classify=True,
                    use_doc_unwarping=True,
                    use_textline_orientation=True,
                    # PP-OCRv6's detection model isn't yet on paddlex's
                    # MKLDNN_BLOCKLIST (the list of models known to break
                    # under oneDNN-accelerated CPU inference) as of
                    # paddlex 3.7.2 -- PP-OCRv6 is new enough that gap
                    # hasn't caught up yet. Left on its default (auto-
                    # enabled when available), construction succeeds but
                    # every real prediction throws "NotImplementedError:
                    # ConvertPirAttribute2RuntimeAttribute not support
                    # [pir::ArrayAttribute<pir::DoubleAttribute>]" deep in
                    # paddle's oneDNN executor -- confirmed directly
                    # against a real install, not a guess. Costs some CPU
                    # inference speed; worth revisiting once paddlex ships
                    # a version with PP-OCRv6 properly blocklisted (or
                    # fixed) upstream.
                    enable_mkldnn=False,
                )
    return _engine


class PaddleOCRProvider(OCRProvider):
    """PP-OCRv6 via the `paddleocr` Python package."""

    name = "paddleocr"

    def read(self, image: Image.Image, config: str = "") -> OCRResult:
        # `config` (the Tesseract-PSM-flag escape hatch on the base
        # interface) is deliberately unused -- see provider.py.
        engine = _get_engine()

        # PaddleOCR reads images in BGR (OpenCV convention); a plain
        # np.asarray(RGB) would swap red and blue channels the model
        # never saw during training.
        rgb = np.asarray(image.convert("RGB"))
        bgr = rgb[:, :, ::-1]

        pages = engine.predict(bgr)
        if not pages:
            return OCRResult(text="", words=[], mean_confidence=None)

        # One np.ndarray image in -> exactly one page result out.
        page = pages[0]
        rec_texts: list[str] = list(page["rec_texts"])
        rec_scores: list[float] = list(page["rec_scores"])
        rec_boxes = page["rec_boxes"]  # Nx4 array of [left, top, right, bottom]

        # One OCRWord per detected *line* here, not per word -- PaddleOCR's
        # recognition granularity is the whole line inside each detected
        # quad, not individual words within it (see OCRWord's docstring).
        words: list[OCRWord] = []
        for i, raw_text in enumerate(rec_texts):
            token = raw_text.strip()
            if not token:
                continue
            confidence = float(rec_scores[i]) * 100 if i < len(rec_scores) else 0.0
            left = top = width = height = 0
            if rec_boxes is not None and len(rec_boxes) > i:
                box_left, box_top, box_right, box_bottom = (float(v) for v in rec_boxes[i])
                left, top = int(box_left), int(box_top)
                width, height = int(box_right - box_left), int(box_bottom - box_top)
            words.append(OCRWord(text=token, confidence=confidence, left=left, top=top, width=width, height=height))

        # Joined one-line-per-OCRWord, in the reading order PaddleOCR
        # already sorted them into (top-to-bottom, then left-to-right --
        # see SortQuadBoxes upstream). Odometer_parser.py's anchor-based
        # text search relies on this reading order to make sense of a
        # dashboard's multiple numbers.
        text = "\n".join(w.text for w in words)
        mean_conf = (sum(w.confidence for w in words) / len(words)) if words else None
        return OCRResult(text=text, words=words, mean_confidence=mean_conf)
