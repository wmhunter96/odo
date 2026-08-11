from __future__ import annotations

from PIL import Image

from .provider import OCRProvider, OCRResult, OCRWord


class TesseractProvider(OCRProvider):
    """Local, free, CPU-only OCR via the Tesseract engine (pytesseract
    bindings). No network access, no GPU required."""

    name = "tesseract"

    def read(self, image: Image.Image) -> OCRResult:
        import pytesseract

        text = pytesseract.image_to_string(image)

        words: list[OCRWord] = []
        try:
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            n = len(data.get("text", []))
            for i in range(n):
                token = (data["text"][i] or "").strip()
                if not token:
                    continue
                try:
                    conf = float(data["conf"][i])
                except (ValueError, TypeError):
                    conf = -1.0
                if conf < 0:
                    continue
                words.append(
                    OCRWord(
                        text=token,
                        confidence=conf,
                        left=int(data["left"][i]),
                        top=int(data["top"][i]),
                        width=int(data["width"][i]),
                        height=int(data["height"][i]),
                    )
                )
        except Exception:
            # image_to_data can fail on some builds/locales; raw text is
            # still useful on its own, so degrade gracefully.
            words = []

        mean_conf = (sum(w.confidence for w in words) / len(words)) if words else None
        return OCRResult(text=text, words=words, mean_confidence=mean_conf)
