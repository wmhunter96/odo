from __future__ import annotations

from PIL import Image

from .provider import OCRProvider, OCRResult, OCRWord


class TesseractProvider(OCRProvider):
    """Local, free, CPU-only OCR via the Tesseract engine (pytesseract
    bindings). No network access, no GPU required."""

    name = "tesseract"

    def read(self, image: Image.Image, config: str = "") -> OCRResult:
        import pytesseract

        # --oem 1 (LSTM engine only) always, regardless of what the caller
        # passed: the Docker image installs Google's "best" (not the apt
        # default "fast") English model specifically to fix systematic
        # misreads a real receipt surfaced -- see the Dockerfile comment --
        # and both the "best" and "fast" tessdata_* packs are LSTM-only
        # data with no legacy-engine model in them. oem 3 ("legacy +
        # LSTM combined", Tesseract's own default) against LSTM-only data
        # is at best a no-op and at worst degrades unpredictably, so this
        # is pinned rather than left to each call site to remember.
        full_config = f"--oem 1 {config}".strip()

        text = pytesseract.image_to_string(image, config=full_config)

        words: list[OCRWord] = []
        try:
            data = pytesseract.image_to_data(image, config=full_config, output_type=pytesseract.Output.DICT)
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
