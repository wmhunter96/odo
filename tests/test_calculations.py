import pytest

from app import calculations


def test_miles_driven():
    assert calculations.miles_driven(401, 821) == 420


def test_miles_driven_no_previous():
    assert calculations.miles_driven(None, 401) is None


def test_miles_driven_non_positive_is_none():
    assert calculations.miles_driven(821, 821) is None
    assert calculations.miles_driven(821, 400) is None


def test_mpg_matches_spec_example():
    # previous=401, current=821, gallons=8.411 -> ~49.934609
    miles = calculations.miles_driven(401, 821)
    mpg = calculations.mpg(miles, 8.411)
    assert mpg == pytest.approx(49.934609, abs=1e-4)


def test_mpg_belongs_to_current_fillup_not_previous():
    derived = calculations.derive(previous_odometer=401, odometer=821, gallons=8.411, fuel_total=37.50)
    assert derived.miles_driven == 420
    assert derived.mpg == pytest.approx(49.934609, abs=1e-4)


def test_cost_per_mile():
    cpm = calculations.cost_per_mile(fuel_total=37.50, miles=420)
    assert cpm == pytest.approx(37.50 / 420)


class _Rec:
    def __init__(self, odometer, gallons, fuel_total):
        self.odometer = odometer
        self.gallons = gallons
        self.fuel_total = fuel_total


def test_annotate_sequence_first_record_has_no_mpg():
    records = [_Rec(401, 7.449, 31.278351), _Rec(821, 8.411, 37.50)]
    annotated = calculations.annotate_sequence(records)
    assert annotated[0].mpg is None
    assert annotated[0].miles_driven is None
    assert annotated[1].mpg == pytest.approx(49.934609, abs=1e-4)
    assert annotated[1].miles_driven == 420


def test_lifetime_mpg_is_distance_over_gallons_not_simple_average():
    # Two intervals with very different MPG and gallons -- lifetime MPG must
    # be the distance/gallons weighted total, not the arithmetic mean of the
    # two individual MPGs (which would ignore that the intervals used
    # different amounts of fuel).
    records = [_Rec(0, 10, 40), _Rec(100, 2, 8), _Rec(600, 5, 20)]
    annotated = calculations.annotate_sequence(records)
    # intervals: 100mi/2gal=50mpg, 500mi/5gal=100mpg
    simple_average = calculations.average_mpg(annotated)
    weighted = calculations.lifetime_mpg(annotated)
    assert simple_average == pytest.approx((50 + 100) / 2)
    assert weighted == pytest.approx(600 / 7)  # 600 total miles / 7 total gallons
    assert weighted != pytest.approx(simple_average)


def test_editing_historical_odometer_updates_downstream_interval():
    records = [_Rec(401, 7.449, 31.278351), _Rec(821, 8.411, 37.50), _Rec(1203, 6.709, 28.78)]
    before = calculations.annotate_sequence(records)
    assert before[1].miles_driven == 420

    records[0].odometer = 411  # correct a typo'd historical reading
    after = calculations.annotate_sequence(records)
    assert after[1].miles_driven == 410
    assert after[1].mpg == pytest.approx(410 / 8.411, abs=1e-6)
    # The interval *before* the edited record is unaffected since it has no predecessor.
    assert after[0].miles_driven is None
