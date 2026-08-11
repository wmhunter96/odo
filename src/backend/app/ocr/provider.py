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
    def read(self, image: Image.Image) -> OCRResult:
        """Run OCR on a preprocessed PIL image and return raw text plus
        word-level boxes/confidences where the engine supports it."""
        raise NotImplementedError
