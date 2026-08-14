"""Receipt field extraction via PaddleOCR-VL-1.6 -- a compact (0.9B) vision-
language document model, not a conventional detect-then-recognize OCR
engine like PP-OCRv6 (see paddle_provider.py, still used for the odometer
photo). Instead of "read every character, then regex the numbers back out"
(the previous architecture), this asks the model directly for the fields
that matter, in a single pass: "here's a receipt photo, here's the schema,
respond with JSON, use null for anything you can't actually read." Paddle
specifically reports this model family is more robust to skew, warping,
and uneven lighting in photographed documents than a plain OCR pass --
exactly the failure modes real gas-receipt photos hit (curled thermal
paper, glare, an angled phone shot) -- so it also needs far less image
preprocessing to work well; see preprocess.py and prepare_for_ocr().

This deliberately does NOT go through the OCRProvider interface
(provider.py) -- that interface's contract (raw text + per-word boxes/
confidences) fits a conventional OCR engine, not a model that returns
already-structured fields directly. Bolting this onto that interface would
mean pretending a JSON object is "text" and inventing fake word boxes for
it, which buys nothing. This module owns the model call and JSON parsing;
receipt_parser.py owns turning that into a validated ReceiptResult --
same separation of concerns as before, just at a different seam.
"""
from __future__ import annotations

import json
import re
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

# "v1.6" specifically -- not just "the latest" -- so a future paddleocr
# upgrade that changes the default doesn't silently switch which model
# this app relies on.
MODEL_NAME = "PaddleOCR-VL-1.6-0.9B"

# Generous but bounded: our schema's JSON output is well under 100 tokens
# in practice, but this caps worst-case generation time (and guards
# against the model rambling instead of stopping) without being so tight
# it could truncate a legitimate response mid-object.
MAX_NEW_TOKENS = 384

# Deliberately spells out the exact JSON shape and field formats rather
# than describing the task in prose and hoping -- a schema the model can
# literally fill in produces far more reliably parseable output than an
# open-ended description does, and pinning date/time to fixed formats
# means _parse_extracted_datetime() below never has to guess between
# "01/24/2026" and "24/01/2026" style ambiguity the way OCR-text date
# parsing used to.
RECEIPT_EXTRACTION_PROMPT = """You are analyzing a photo of a gas station fuel receipt.

Respond with ONLY a single JSON object -- no explanation, no markdown code fence -- matching exactly this shape:

{
  "station_name": string or null,
  "address": string or null,
  "date": string or null,
  "time": string or null,
  "pump_number": integer or null,
  "fuel_type": string or null,
  "gallons": number or null,
  "price_per_gallon": number or null,
  "total": number or null
}

Rules:
- "date" must be "YYYY-MM-DD". "time" must be 24-hour "HH:MM:SS" (use "HH:MM:00" if seconds aren't printed).
- "gallons", "price_per_gallon", and "total" must be plain JSON numbers (e.g. 5.422), never strings, and never include a "$" sign.
- Do not guess a value you cannot actually read on the receipt -- use null instead of a best guess.
- gallons multiplied by price_per_gallon should be approximately equal to total; if the numbers you read don't satisfy that, re-check them before answering.
- Respond with the JSON object only, nothing before or after it."""

_engine_lock = threading.Lock()
_engine: Any = None


def _get_engine() -> Any:
    """Lazily construct and cache the DocUnderstanding pipeline running
    PaddleOCR-VL-1.6. Same rationale as paddle_provider._get_engine():
    building it loads real model weights, so it happens once per process,
    guarded by a lock since FastAPI can have more than one request in
    flight."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from paddleocr import DocUnderstanding

                _engine = DocUnderstanding(doc_understanding_model_name=MODEL_NAME)
    return _engine


@dataclass
class ReceiptExtraction:
    """Raw output of one receipt photo's VLM extraction pass, before
    receipt_parser.py normalizes/validates it into a ReceiptResult.

    `fields` is the parsed JSON object on success, or None if the model's
    response wasn't valid JSON (a malformed/truncated response, or the
    model ignoring the "JSON only" instruction) -- distinguished from a
    field simply being present-but-null, which is a normal, expected
    outcome the prompt explicitly asks for and receipt_parser.py handles
    as "not on the receipt", not an error.
    """

    raw_response: str
    fields: dict[str, Any] | None
    error: str | None = None


# The model is asked for a bare JSON object, but "no markdown code fence"
# doesn't always hold in practice -- strip a ```json ... ``` (or bare ```
# ... ```) wrapper if present before attempting to parse, rather than
# failing on formatting the prompt already tried to rule out.
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)
# Last-resort fallback if the response has stray text before/after the
# object despite the prompt -- grab the first balanced-looking {...} span.
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_response(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    fence_match = _CODE_FENCE_RE.match(stripped)
    if fence_match:
        stripped = fence_match.group(1).strip()

    try:
        parsed = json.loads(stripped)
    except (ValueError, TypeError):
        obj_match = _JSON_OBJECT_RE.search(stripped)
        if not obj_match:
            return None
        try:
            parsed = json.loads(obj_match.group(0))
        except (ValueError, TypeError):
            return None

    return parsed if isinstance(parsed, dict) else None


def extract_receipt_fields(image: Image.Image) -> ReceiptExtraction:
    """Runs the receipt photo through PaddleOCR-VL-1.6 and returns its
    parsed JSON response. Never raises -- a model/inference failure or an
    unparseable response comes back as a ReceiptExtraction with
    fields=None and `error` set, for parse_receipt() to turn into a
    normal "couldn't read this" warning rather than a 500."""
    try:
        engine = _get_engine()
    except Exception as exc:  # pragma: no cover - exercised via mocks in tests
        return ReceiptExtraction(raw_response="", fields=None, error=f"Failed to load the extraction model: {exc}")

    # The documented `{"image": ..., "query": ...}` input takes a path/URL,
    # not an in-memory array (unlike the plain OCR pipeline) -- written to
    # a throwaway temp file rather than gambling on undocumented array
    # support for this particular pipeline.
    try:
        with tempfile.TemporaryDirectory(prefix="odo-receipt-vlm-") as tmp_dir:
            image_path = Path(tmp_dir) / "receipt.jpg"
            image.convert("RGB").save(image_path, "JPEG", quality=92)

            pages = engine.predict(
                {"image": str(image_path), "query": RECEIPT_EXTRACTION_PROMPT},
                max_new_tokens=MAX_NEW_TOKENS,
            )
    except Exception as exc:  # pragma: no cover - exercised via mocks in tests
        return ReceiptExtraction(raw_response="", fields=None, error=f"Receipt extraction failed: {exc}")

    if not pages:
        return ReceiptExtraction(raw_response="", fields=None, error="Model returned no result.")

    raw = pages[0]["result"]
    # A single (image, query) pair is one prediction -- but the pipeline's
    # result-formatting always builds "result" as a per-sample list (see
    # format_doc_vlm_result_dict in paddlex), so unwrap a length-1 list
    # rather than assume either shape.
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    raw_response = str(raw)

    fields = _parse_json_response(raw_response)
    if fields is None:
        return ReceiptExtraction(
            raw_response=raw_response, fields=None, error="Model response was not valid JSON."
        )
    return ReceiptExtraction(raw_response=raw_response, fields=fields)
