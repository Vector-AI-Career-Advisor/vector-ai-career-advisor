from server.etl.utils import company_slug


def test_basic_slugify():
    assert company_slug("Chainalysis") == "chainalysis"
    assert company_slug("Experis Israel") == "experis-israel"
    assert company_slug("  BioCatch  ") == "biocatch"


def test_punctuation_and_symbols_collapse():
    assert company_slug("AT&T") == "at-t"
    assert company_slug("Booking.com") == "booking-com"
    assert company_slug("Yotpo — Ltd.") == "yotpo-ltd"


def test_unicode_is_transliterated():
    assert company_slug("Naïve Café") == "naive-cafe"


def test_blank_and_placeholder_names_return_none():
    for name in ("", "   ", "N/A", "n/a", "NA", "None", "unknown", None):
        assert company_slug(name) is None


def test_idempotent():
    once = company_slug("Some Company, Inc.")
    assert once == company_slug(once)
