from server.etl.locations import normalize_location


def test_known_cities_get_city_and_region():
    assert normalize_location("Tel Aviv-Yafo") == ("Tel Aviv-Yafo", "Tel Aviv")
    assert normalize_location("Ramat Gan") == ("Ramat Gan", "Center")
    assert normalize_location("Herzliya") == ("Herzliya", "Sharon")
    assert normalize_location("Ashdod") == ("Ashdod", "South")


def test_transliteration_variants_collapse():
    assert normalize_location("Yoqneam Illit") == ("Yokneam Illit", "North")
    assert normalize_location("Yokneam Ilit") == ("Yokneam Illit", "North")
    assert normalize_location("Raanana") == ("Ra'anana", "Sharon")
    assert normalize_location("Petach Tikva") == ("Petah Tikva", "Center")


def test_country_suffix_stripped():
    assert normalize_location("Netanya, Israel") == ("Netanya", "Sharon")
    assert normalize_location("  Haifa , Israel ") == ("Haifa", "Haifa")


def test_district_rows_have_region_only():
    assert normalize_location("Center District, Israel") == (None, "Center")
    assert normalize_location("Tel Aviv District, Israel") == (None, "Tel Aviv")
    assert normalize_location("North District, Israel") == (None, "North")


def test_city_wins_over_bare_region_name():
    # "Haifa" / "Jerusalem" are both a city and a district — city reading wins
    assert normalize_location("Haifa") == ("Haifa", "Haifa")
    assert normalize_location("Jerusalem") == ("Jerusalem", "Jerusalem")
    # but a bare region word with no matching city stays region-only
    assert normalize_location("Center") == (None, "Center")


def test_blank_and_country_only():
    for v in ("Israel", "", "  ", None, "N/A", "unknown"):
        assert normalize_location(v) == (None, None)


def test_remote():
    assert normalize_location("Remote") == ("Remote", "Remote")
    assert normalize_location("Remote - Israel") == ("Remote", "Remote")


def test_unknown_city_kept_without_region():
    assert normalize_location("Someplace New") == ("Someplace New", None)


def test_idempotent_on_city_output():
    # feeding the canonical city back in returns the same pair
    for raw in ("Yoqneam Ilit", "Ramat Gan", "Tel Aviv-Yafo", "Haifa"):
        city, region = normalize_location(raw)
        assert normalize_location(city) == (city, region)
