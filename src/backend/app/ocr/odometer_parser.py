"""Extract the odometer reading from raw OCR output of a dashboard photo.

A dashboard photo typically contains several numbers: the odometer, trip
meter(s), fuel range, outside temperature, clock, MPG, etc. We can't rely on
"the biggest number wins" or "the first number wins" -- instead every digit
run is scored as a candidate and the best-scoring one is returned, along
with the runner-up candidates so the UI can offer them if OCR guessed wrong.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .provider import OCRResult

# Odometers are virtually always a plain integer, 3-7 digits, sometimes with
# thousands separators (e.g. "18,442") or a trailing "mi"/"km" unit. Trip
# meters/MPG/etc usually carry a decimal point (e.g. "421.6"), which we
# deliberately treat as lower priority. The comma-grouped alternative is
# tried first so "18,442" isn't split into "18" and "442"; the plain digit
# run handles ungrouped numbers like "18442".
_NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")

# Many dashboards print the odometer flanked by the literal strings "ODO"
# and "mi" (e.g. "ODO  4090mi"). Both are short, high-contrast text that
# tends to survive OCR intact even when the surrounding numbers (speed,
# range, clock, tire-pressure digits, gauge tick labels, ...) get misread
# or the digit run itself gets split -- so when both anchors are present
# this is a far stronger signal than the generic scoring below and is
# checked first. Only the digit characters between the two anchors are
# kept; any stray misread character OCR drops in there (e.g. a smudge read
# as a letter) is discarded rather than treated as part of the number.
_ODO_ANCHOR_RE = re.compile(
    r"ODO\b[^0-9]{0,10}([0-9][0-9,.\s]{0,10}[0-9]|[0-9])[^0-9A-Za-z]{0,5}mi\b",
    re.IGNORECASE,
)


@dataclass
class OdometerCandidate:
    value: float
    raw_text: str
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class OdometerResult:
    value: float | None
    confidence: float
    candidates: list[OdometerCandidate]
    raw_text: str


def _clean_number(raw: str) -> float:
    return float(raw.replace(",", "").replace(" ", ""))


def _iter_number_tokens(text: str):
    for m in _NUMBER_RE.finditer(text):
        yield m.group(0)


def parse_odometer(result: OCRResult, previous_odometer: float | None = None) -> OdometerResult:
    text = result.text or ""
    candidates: list[OdometerCandidate] = []

    # Build a lookup of OCR word confidences/heights for tokens that came
    # from word-level data, to prefer visually larger/higher-confidence text.
    word_meta = {w.text.strip(): w for w in result.words if w.text.strip()}
    max_height = max((w.height for w in result.words), default=0) or 1

    seen_values: set[float] = set()

    anchor_match = _ODO_ANCHOR_RE.search(text)
    if anchor_match:
        digits_only = re.sub(r"[^\d]", "", anchor_match.group(1))
        if digits_only:
            try:
                anchor_value = float(digits_only)
            except ValueError:
                anchor_value = None
            if anchor_value is not None:
                seen_values.add(anchor_value)
                candidates.append(
                    OdometerCandidate(
                        value=anchor_value,
                        raw_text=anchor_match.group(0),
                        # Comfortably higher than anything the generic
                        # scoring loop below can produce (its max is
                        # roughly 3 + 2 + 2 + 3 = 10) so this always wins
                        # when both anchors are found.
                        score=20.0,
                        reasons=["found between 'ODO' and 'mi' anchors"],
                    )
                )

    for token in _iter_number_tokens(text):
        digits_only = re.sub(r"[^\d]", "", token.split(".")[0])
        has_decimal = "." in token
        if not digits_only:
            continue
        try:
            value = _clean_number(token)
        except ValueError:
            continue

        length = len(digits_only)
        reasons: list[str] = []
        score = 0.0

        # Plausible odometer digit-length range for a passenger car.
        if 3 <= length <= 6:
            score += 3
            reasons.append("plausible length")
        elif length == 7:
            score += 1
            reasons.append("long but possible")
        else:
            score -= 3
            reasons.append("implausible length")

        if has_decimal:
            score -= 2
            reasons.append("has decimal (likely trip/MPG)")

        meta = word_meta.get(token)
        if meta is not None:
            score += (meta.confidence / 100) * 2
            reasons.append(f"ocr confidence {meta.confidence:.0f}")
            score += (meta.height / max_height) * 2
            reasons.append("relative text size")

        if previous_odometer is not None:
            if value >= previous_odometer:
                delta = value - previous_odometer
                if delta <= 2000:
                    score += 3
                    reasons.append("close to expected next reading")
                elif delta <= 10000:
                    score += 1
                    reasons.append("plausible relative to history")
                else:
                    score -= 1
                    reasons.append("far above previous reading")
            else:
                score -= 2
                reasons.append("lower than previous reading")

        if value in seen_values:
            continue
        seen_values.add(value)
        candidates.append(OdometerCandidate(value=value, raw_text=token, score=score, reasons=reasons))

    candidates.sort(key=lambda c: c.score, reverse=True)

    if not candidates:
        return OdometerResult(value=None, confidence=0.0, candidates=[], raw_text=text)

    best = candidates[0]
    # Normalize score into a rough 0-100 confidence.
    confidence = max(0.0, min(100.0, 40 + best.score * 10))
    return OdometerResult(value=best.value, confidence=confidence, candidates=candidates[:5], raw_text=text)
