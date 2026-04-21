import pytest
from quinex.normalize.temporal_scope.year import get_int_year_from_temporal_scope



# ---------------------------------------------------------------------------
# Explicit year extraction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("span,expected", [
    ("in 2021", 2021),
    ("by 2030", 2030),
    ("2019", 2019),
    ("year 2025", 2025),
    ("starting in 2018", 2018),
])
def test_explicit_year_extracted(span, expected):
    year, assumed = get_int_year_from_temporal_scope(span, 2000)
    assert year == expected
    assert assumed is False


# ---------------------------------------------------------------------------
# Out-of-bounds
# ---------------------------------------------------------------------------

def test_year_below_lower_bound_falls_back_to_pub_year():
    year, assumed = get_int_year_from_temporal_scope("in 1700", 2020, allowed_year_lb=1800)
    assert year == 2020
    assert assumed is True

def test_year_above_upper_bound_falls_back_to_pub_year():
    year, assumed = get_int_year_from_temporal_scope("in 2200", 2020, allowed_year_ub=2100)
    assert year == 2020
    assert assumed is True


# ---------------------------------------------------------------------------
# Present-tense keywords
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("span", [
    "currently",
    "presently",
    "today",
    "today's",
    "current",
    "current level",
    "current status",
    "nowadays",
    "present-day",
])
def test_currently_keywords_return_pub_year(span):
    year, assumed = get_int_year_from_temporal_scope(span, 2020)
    assert year == 2020
    assert assumed is False


# ---------------------------------------------------------------------------
# Future and historical relative keywords
# ---------------------------------------------------------------------------

def test_short_term_future_keywords():
    year, assumed = get_int_year_from_temporal_scope("short-term future", 2020, shortterm_in_years=5)
    assert year == 2025
    assert assumed is False  # TODO: Switch to assumed=True for short-term future?

def test_mid_term_future_keywords():
    year, assumed = get_int_year_from_temporal_scope("mid-term future", 2020, midterm_in_years=10)
    assert year == 2030
    assert assumed is True

def test_long_term_future_keywords():
    year, assumed = get_int_year_from_temporal_scope("long-term future", 2020, longterm_in_years=20)
    assert year == 2040
    assert assumed is True

def test_recently_keywords():
    year, assumed = get_int_year_from_temporal_scope("recently commissioned", 2020, recently_in_years=-5)
    assert year == 2015
    assert assumed is False  # TODO: Switch to assumed=True for recently?


# ---------------------------------------------------------------------------
# Superfluous chars in input
# ---------------------------------------------------------------------------

def test_trailing_period_stripped():    
    year, assumed = get_int_year_from_temporal_scope("in 2022.", 2000)
    assert year == 2022
    assert assumed is False


# ---------------------------------------------------------------------------
# Empty, none, and invalid input
# ---------------------------------------------------------------------------

def test_no_year_found_falls_back_to_pub_year():
    year, assumed = get_int_year_from_temporal_scope("no year here", 2021)
    assert year == 2021
    assert assumed is True

def test_empty_string_returns_publication_year():
    year, assumed = get_int_year_from_temporal_scope("", 2021)
    assert year == 2021
    assert assumed is True

def test_none_pub_year_with_empty_string():
    year, assumed = get_int_year_from_temporal_scope("", None)
    assert year is None
    assert assumed is True

def test_invalid_pub_year_type_raises():
    with pytest.raises(ValueError):
        get_int_year_from_temporal_scope("", "2021")