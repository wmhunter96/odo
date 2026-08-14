"""OCR provider interface.

Any local OCR engine can be plugged in by implementing `OCRProvider`. This
keeps the rest of the app (parsers, routes, validation) completely
independent of which engine actually reads the pixels.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from PIL import Image


@dataclass
class OCRWord:
    """One recognized span of text with its bounding box and confidence.

    Named "word" for historical reasons (the first provider was
    word-granular), but the actual granularity is whatever the engine
    naturally detects as one unit -- a line-detection engine like
    PaddleOCR reports one OCRWord per detected text line, not per word.
    Callers that need exact word boundaries shouldn't assume either way;
    everything downstream (parsers) works off of `OCRResult.text` instead
    and only uses these for confidence/position, where "roughly the right
    line" is good enough.
    """

    text: str
    confidence: float  # 0-100
    left: int
    top: int
    width: int
    height: int


@dataclass
class OCRResult:
    text: str
    words: list[OCRWord] = field(default_factory=list)
    mean_confidence: float | None = None


class OCRProvider(ABC):
    name: str = "base"

    @abstractmethod
    def read(self, image: Image.Image, config: str = "") -> OCRResult:
        """Run OCR on a preprocessed PIL image and return raw text plus
        word-level boxes/confidences where the engine supports it.

        `config` is an escape hatch for engine-specific tuning flags,
        passed through verbatim so callers can tune per image type without
        the provider interface knowing what "receipt" or "odometer" mean.
        Not every engine takes one -- PaddleOCRProvider ignores it, since
        PaddleOCR's detector finds text regions on its own rather than
        needing a page-layout hint the way Tesseract's PSM did.
        """
        raise NotImplementedError
