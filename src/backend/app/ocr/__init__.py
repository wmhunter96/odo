"""OCR subsystem.

Image -> preprocess -> OCR engine (provider) -> raw text/words -> field
parser -> candidate values. The engine is swappable behind `OCRProvider`
(see provider.py) -- currently PaddleOCR (PP-OCRv6), previously Tesseract
-- without touching preprocessing, parsing, or the API layer. Swapping
engines again later means adding a new *_provider.py implementing
OCRProvider and pointing get_provider() at it; nothing else in the OCR
subsystem needs to know or care.
"""
from .paddle_provider import PaddleOCRProvider
from .provider import OCRProvider, OCRResult, OCRWord

__all__ = ["OCRProvider", "OCRResult", "OCRWord", "PaddleOCRProvider", "get_provider"]


def get_provider(name: str = "paddleocr") -> OCRProvider:
    if name == "paddleocr":
        return PaddleOCRProvider()
    raise ValueError(f"Unknown OCR engine: {name}")
