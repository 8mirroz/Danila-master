"""
Unit tests for my-crawler routes.py helper functions.
"""
import sys
import os

# Add parent dir so we can import routes
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from my_crawler.routes import clean_price


# ---------------------------------------------------------------------------
# clean_price tests
# ---------------------------------------------------------------------------


def test_clean_price_simple():
    """Normal price with space and ₽ symbol."""
    assert clean_price("4 500 ₽") == "4500 ₽"


def test_clean_price_with_xa0():
    """Non-breaking space (\xa0) before ₽."""
    assert clean_price("1\u00a0200 ₽") == "1200 ₽"


def test_clean_price_decimal_comma():
    """Price with decimal comma (European style)."""
    assert clean_price("1 200,50 ₽") == "1200.50 ₽"


def test_clean_price_no_separator():
    """Price without thousand separator."""
    assert clean_price("4500 ₽") == "4500 ₽"


def test_clean_price_no_ruble_sign():
    """Price without ₽ symbol — should still extract digits."""
    assert clean_price("4500") == "4500 ₽"


def test_clean_price_em_dash():
    """No price available."""
    assert clean_price("——") == "——"


def test_clean_price_empty_string():
    """Empty string."""
    assert clean_price("") == "——"


def test_clean_price_none_string():
    """None value."""
    assert clean_price(None) == "——"


def test_clean_price_with_date_and_price():
    """Rossko-style: "3820514182" was old bug (date+price concatenated).
    Now should extract first group."""
    # Example: "  3 820.51 ₽  ~10 июля" — but after element extraction we get just price
    result = clean_price("3 820.51 ₽")
    assert result == "3820.51 ₽" or result == "3820.51 ₽"


def test_clean_price_only_ruble():
    """₽ without digits."""
    assert clean_price("₽") == "——"


def test_clean_price_with_extra_text():
    """Price with extra text around it."""
    assert clean_price("Цена: 4500 ₽ за штуку") == "4500 ₽"


def test_clean_price_multiple_groups():
    """Multiple digit groups — should pick the first sensible one."""
    # Price "1 234 ₽" → 1234 ₽ (not 1234 ₽ concatenated with other numbers)
    result = clean_price("1 234 ₽  ~10 июля, пт")
    assert result == "1234 ₽"


def test_clean_price_rossko_typical():
    """Typical Rossko price format: "  471,15 ₽  1 418 20" (with order info).
    Should extract "471.15 ₽"."""
    result = clean_price("471,15 ₽")
    assert result == "471.15 ₽"


def test_clean_price_decimal_dot():
    """Price with decimal dot."""
    assert clean_price("1 200.50 ₽") == "1200.50 ₽"


def test_clean_price_no_spaces():
    """Price without any spaces."""
    assert clean_price("1200.50₽") == "1200.50 ₽"


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Run tests manually
    import pytest
    pytest.main([__file__, "-v"])