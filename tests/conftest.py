from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def historical_csv_text() -> str:
    return (FIXTURES_DIR / "historical_sample.csv").read_text(encoding="utf-8")
