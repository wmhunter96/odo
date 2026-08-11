"""OCR subsystem.

Image -> preprocess -> OCR engine (provider) -> raw text/words -> field
parser -> candidate values. The engine is swappable behind `OCRProvider`
(see provider.py) so Tesseract can be replaced later (PaddleOCR, etc.)
without touching preprocessing, parsing, or the API layer.
"""
from .provider import OCRProvider, OCRResult, OCRWord
from .tesseract_provider import TesseractProvider

__all__ = ["OCRProvider", "OCRResult", "OCRWord", "TesseractProvider", "get_provider"]


def get_provider(name: str = "tesseract") -> OCRProvider:
    if name == "tesseract":
        return TesseractProvider()
    raise ValueError(f"Unknown OCR engine: {name}")
