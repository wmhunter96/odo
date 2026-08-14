"""extract_receipt_fields() must correctly configure and call PaddleOCR-VL-
1.6 via the DocUnderstanding pipeline, and must never raise -- a model or
inference failure, or a response that isn't valid JSON, comes back as a
ReceiptExtraction with fields=None and `error` set instead.

Mocked so this runs without `paddleocr`/`paddlepaddle` (and the model's own
weights) installed, same rationale as test_paddle_provider.py.
"""
import sys
import types
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

import app.ocr.receipt_vlm as receipt_vlm_module
from app.ocr.receipt_vlm import extract_receipt_fields


@pytest.fixture(autouse=True)
def _reset_cached_engine():
    receipt_vlm_module._engine = None
    yield
    receipt_vlm_module._engine = None


def _blank_image() -> Image.Image:
    return Image.new("RGB", (10, 10), (255, 255, 255))


def _install_fake_paddleocr(predict_return):
    """Installs a fake `paddleocr` module in sys.modules (extract_receipt_
    fields does `from paddleocr import DocUnderstanding` lazily, inside
    _get_engine) so the import succeeds without the real package."""
    fake_module = types.ModuleType("paddleocr")
    mock_cls = MagicMock(return_value=MagicMock(predict=MagicMock(return_value=predict_return)))
    fake_module.DocUnderstanding = mock_cls
    return patch.dict(sys.modules, {"paddleocr": fake_module}), mock_cls


def _page(result):
    return {"result": result}


def test_uses_paddleocr_vl_1_6_model():
    ctx, mock_cls = _install_fake_paddleocr([_page("{}")])
    with ctx:
        extract_receipt_fields(_blank_image())

    assert mock_cls.call_args.kwargs["doc_understanding_model_name"] == "PaddleOCR-VL-1.6-0.9B"


def test_engine_is_built_once_and_reused_across_calls():
    ctx, mock_cls = _install_fake_paddleocr([_page("{}")])
    with ctx:
        extract_receipt_fields(_blank_image())
        extract_receipt_fields(_blank_image())

    assert mock_cls.call_count == 1


def test_query_is_the_receipt_field_extraction_prompt():
    ctx, mock_cls = _install_fake_paddleocr([_page("{}")])
    with ctx:
        extract_receipt_fields(_blank_image())

    predict_mock = mock_cls.return_value.predict
    call_kwargs = predict_mock.call_args.args[0]
    assert call_kwargs["query"] == receipt_vlm_module.RECEIPT_EXTRACTION_PROMPT
    assert "station_name" in call_kwargs["query"]
    assert "gallons" in call_kwargs["query"]
    assert predict_mock.call_args.kwargs["max_new_tokens"] == receipt_vlm_module.MAX_NEW_TOKENS


def test_clean_json_response_is_parsed():
    raw = '{"station_name": "PRO MART", "gallons": 5.422, "total": 21.14}'
    ctx, _ = _install_fake_paddleocr([_page(raw)])
    with ctx:
        result = extract_receipt_fields(_blank_image())

    assert result.error is None
    assert result.fields == {"station_name": "PRO MART", "gallons": 5.422, "total": 21.14}
    assert result.raw_response == raw


def test_result_wrapped_in_a_length_one_list_is_unwrapped():
    # format_doc_vlm_result_dict (paddlex) always builds "result" as a
    # per-sample list -- a single (image, query) call still comes back
    # list-wrapped, not a bare string.
    raw = '{"gallons": 5.422}'
    ctx, _ = _install_fake_paddleocr([_page([raw])])
    with ctx:
        result = extract_receipt_fields(_blank_image())

    assert result.fields == {"gallons": 5.422}


def test_markdown_code_fence_is_stripped_before_parsing():
    raw = '```json\n{"gallons": 5.422}\n```'
    ctx, _ = _install_fake_paddleocr([_page(raw)])
    with ctx:
        result = extract_receipt_fields(_blank_image())

    assert result.fields == {"gallons": 5.422}


def test_stray_text_around_the_json_object_is_recovered():
    raw = 'Sure, here is the JSON:\n{"gallons": 5.422}\nLet me know if you need anything else.'
    ctx, _ = _install_fake_paddleocr([_page(raw)])
    with ctx:
        result = extract_receipt_fields(_blank_image())

    assert result.fields == {"gallons": 5.422}


def test_unparseable_response_returns_fields_none_with_an_error():
    raw = "I'm not able to read this receipt clearly."
    ctx, _ = _install_fake_paddleocr([_page(raw)])
    with ctx:
        result = extract_receipt_fields(_blank_image())

    assert result.fields is None
    assert result.error is not None
    assert result.raw_response == raw


def test_json_array_response_is_rejected_not_treated_as_fields():
    # Valid JSON, but not an object -- must not be silently accepted as a
    # dict-like fields mapping (which .get() calls downstream assume).
    raw = "[1, 2, 3]"
    ctx, _ = _install_fake_paddleocr([_page(raw)])
    with ctx:
        result = extract_receipt_fields(_blank_image())

    assert result.fields is None


def test_no_pages_returned_degrades_gracefully():
    ctx, _ = _install_fake_paddleocr([])
    with ctx:
        result = extract_receipt_fields(_blank_image())

    assert result.fields is None
    assert result.error is not None


def test_model_call_raising_is_caught_not_propagated():
    fake_module = types.ModuleType("paddleocr")
    mock_cls = MagicMock(return_value=MagicMock(predict=MagicMock(side_effect=RuntimeError("inference failed"))))
    fake_module.DocUnderstanding = mock_cls
    with patch.dict(sys.modules, {"paddleocr": fake_module}):
        result = extract_receipt_fields(_blank_image())

    assert result.fields is None
    assert result.error is not None
    assert "inference failed" in result.error
