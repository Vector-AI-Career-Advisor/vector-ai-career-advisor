"""
Location normalisation.

Scraped locations are a mix of cities ("Tel Aviv-Yafo", "Ramat Gan"),
districts ("Center District, Israel"), transliteration variants ("Yoqneam
Illit" vs "Yokneam Ilit") and bare "Israel". `normalize_location()` maps a raw
string to a (city, region) pair:

  - city   — canonical spelling, or None when the source only gave a district
  - region — one of the seven values in REGIONS, or None when unknown

The ETL stores both (jobs.location = city, jobs.region = region); the region is
what the sidebar's region filter matches against. Kept in sync with the
client-side copy in client/src/lib/locations.ts.
"""
from __future__ import annotations

import re

REGIONS = ("Tel Aviv", "Center", "Sharon", "Haifa", "North", "South", "Jerusalem")

# Raw / variant spelling (lower-case) → (canonical city, region).
_CITIES: dict[str, tuple[str, str]] = {
    # ── Tel Aviv ──────────────────────────────────────────────────────────────
    "tel aviv-yafo": ("Tel Aviv-Yafo", "Tel Aviv"),
    "tel aviv": ("Tel Aviv-Yafo", "Tel Aviv"),
    "tel-aviv": ("Tel Aviv-Yafo", "Tel Aviv"),
    "tel aviv-jaffa": ("Tel Aviv-Yafo", "Tel Aviv"),
    "tel aviv yafo": ("Tel Aviv-Yafo", "Tel Aviv"),
    # ── Center (Gush Dan + Shfela) ────────────────────────────────────────────
    "ramat gan": ("Ramat Gan", "Center"),
    "givatayim": ("Giv'atayim", "Center"),
    "giv'atayim": ("Giv'atayim", "Center"),
    "bnei brak": ("Bnei Brak", "Center"),
    "petah tikva": ("Petah Tikva", "Center"),
    "petach tikva": ("Petah Tikva", "Center"),
    "petah tiqwa": ("Petah Tikva", "Center"),
    "holon": ("Holon", "Center"),
    "bat yam": ("Bat Yam", "Center"),
    "rishon lezion": ("Rishon LeZion", "Center"),
    "rishon leziyyon": ("Rishon LeZion", "Center"),
    "rishon le zion": ("Rishon LeZion", "Center"),
    "rehovot": ("Rehovot", "Center"),
    "ness ziona": ("Ness Ziona", "Center"),
    "nes ziona": ("Ness Ziona", "Center"),
    "yavne": ("Yavne", "Center"),
    "lod": ("Lod", "Center"),
    "ramla": ("Ramla", "Center"),
    "rosh haayin": ("Rosh HaAyin", "Center"),
    "rosh ha'ayin": ("Rosh HaAyin", "Center"),
    "or yehuda": ("Or Yehuda", "Center"),
    "yehud": ("Yehud-Monosson", "Center"),
    "yehud monosson": ("Yehud-Monosson", "Center"),
    "yehud-monosson": ("Yehud-Monosson", "Center"),
    "givat shmuel": ("Giv'at Shmuel", "Center"),
    "giv'at shmuel": ("Giv'at Shmuel", "Center"),
    "beer yaakov": ("Be'er Ya'akov", "Center"),
    "be'er ya'akov": ("Be'er Ya'akov", "Center"),
    "modiin": ("Modi'in-Maccabim-Re'ut", "Center"),
    "modi'in": ("Modi'in-Maccabim-Re'ut", "Center"),
    "modiin-maccabim-reut": ("Modi'in-Maccabim-Re'ut", "Center"),
    "modi'in-maccabim-re'ut": ("Modi'in-Maccabim-Re'ut", "Center"),
    "elad": ("El'ad", "Center"),
    "gedera": ("Gedera", "Center"),
    # ── Sharon ────────────────────────────────────────────────────────────────
    "herzliya": ("Herzliya", "Sharon"),
    "herzeliya": ("Herzliya", "Sharon"),
    "raanana": ("Ra'anana", "Sharon"),
    "ra'anana": ("Ra'anana", "Sharon"),
    "kfar saba": ("Kfar Saba", "Sharon"),
    "kfar sava": ("Kfar Saba", "Sharon"),
    "hod hasharon": ("Hod HaSharon", "Sharon"),
    "ramat hasharon": ("Ramat HaSharon", "Sharon"),
    "netanya": ("Netanya", "Sharon"),
    "nathanya": ("Netanya", "Sharon"),
    "even yehuda": ("Even Yehuda", "Sharon"),
    "kadima": ("Kadima-Zoran", "Sharon"),
    "kadima-zoran": ("Kadima-Zoran", "Sharon"),
    "tel mond": ("Tel Mond", "Sharon"),
    "pardes hanna": ("Pardes Hanna-Karkur", "Sharon"),
    "pardes hanna-karkur": ("Pardes Hanna-Karkur", "Sharon"),
    # ── Haifa ─────────────────────────────────────────────────────────────────
    "haifa": ("Haifa", "Haifa"),
    "nesher": ("Nesher", "Haifa"),
    "kiryat bialik": ("Kiryat Bialik", "Haifa"),
    "kiryat ata": ("Kiryat Ata", "Haifa"),
    "kiryat motzkin": ("Kiryat Motzkin", "Haifa"),
    "kiryat yam": ("Kiryat Yam", "Haifa"),
    "tirat carmel": ("Tirat Carmel", "Haifa"),
    "caesarea": ("Caesarea", "Haifa"),
    "or akiva": ("Or Akiva", "Haifa"),
    "zichron yaakov": ("Zichron Ya'akov", "Haifa"),
    "zikhron ya'akov": ("Zichron Ya'akov", "Haifa"),
    "hadera": ("Hadera", "Haifa"),
    # ── North ─────────────────────────────────────────────────────────────────
    "yokneam": ("Yokneam Illit", "North"),
    "yokneam illit": ("Yokneam Illit", "North"),
    "yokneam ilit": ("Yokneam Illit", "North"),
    "yoqneam illit": ("Yokneam Illit", "North"),
    "yoqneam ilit": ("Yokneam Illit", "North"),
    "karmiel": ("Karmiel", "North"),
    "nazareth": ("Nazareth", "North"),
    "nof hagalil": ("Nof HaGalil", "North"),
    "migdal haemek": ("Migdal HaEmek", "North"),
    "migdal haemeq": ("Migdal HaEmek", "North"),
    "afula": ("Afula", "North"),
    "tiberias": ("Tiberias", "North"),
    "acre": ("Acre", "North"),
    "akko": ("Acre", "North"),
    "nahariya": ("Nahariya", "North"),
    "safed": ("Safed", "North"),
    "tzfat": ("Safed", "North"),
    "kiryat shmona": ("Kiryat Shmona", "North"),
    "migdal tefen": ("Migdal Tefen", "North"),
    "tefen": ("Migdal Tefen", "North"),
    "ein harod": ("Ein Harod", "North"),
    "ramot menashe": ("Ramot Menashe", "North"),
    "beit shean": ("Beit She'an", "North"),
    "beit she'an": ("Beit She'an", "North"),
    "shlomi": ("Shlomi", "North"),
    "maalot": ("Ma'alot-Tarshiha", "North"),
    "maalot-tarshiha": ("Ma'alot-Tarshiha", "North"),
    # ── South ─────────────────────────────────────────────────────────────────
    "beer sheva": ("Be'er Sheva", "South"),
    "be'er sheva": ("Be'er Sheva", "South"),
    "beersheba": ("Be'er Sheva", "South"),
    "ashdod": ("Ashdod", "South"),
    "ashkelon": ("Ashkelon", "South"),
    "kiryat gat": ("Kiryat Gat", "South"),
    "kiryat malachi": ("Kiryat Malakhi", "South"),
    "sderot": ("Sderot", "South"),
    "netivot": ("Netivot", "South"),
    "ofakim": ("Ofakim", "South"),
    "dimona": ("Dimona", "South"),
    "arad": ("Arad", "South"),
    "eilat": ("Eilat", "South"),
    "yeruham": ("Yeruham", "South"),
    "rahat": ("Rahat", "South"),
    # ── Jerusalem ─────────────────────────────────────────────────────────────
    "jerusalem": ("Jerusalem", "Jerusalem"),
    "west jerusalem": ("Jerusalem", "Jerusalem"),
    "beit shemesh": ("Beit Shemesh", "Jerusalem"),
    "mevaseret zion": ("Mevaseret Zion", "Jerusalem"),
    "maale adumim": ("Ma'ale Adumim", "Jerusalem"),
}

# District / region words (lower-case, "district" stripped) → region.
_DISTRICT_REGION: dict[str, str] = {
    "tel aviv": "Tel Aviv",
    "center": "Center",
    "central": "Center",
    "merkaz": "Center",
    "haifa": "Haifa",
    "north": "North",
    "northern": "North",
    "south": "South",
    "southern": "South",
    "jerusalem": "Jerusalem",
    "sharon": "Sharon",
    "hasharon": "Sharon",
}

_WS_RE = re.compile(r"\s+")
_COUNTRY_SUFFIX_RE = re.compile(r",\s*(israel|isr|il|ישראל)\s*$", re.IGNORECASE)
_DISTRICT_WORD_RE = re.compile(r"\bdistrict\b|מחוז", re.IGNORECASE)
_BLANK = {"", "israel", "il", "isr", "n/a", "na", "none", "null", "unknown", "-"}


def normalize_location(raw: str | None) -> tuple[str | None, str | None]:
    """Return (canonical_city, region) for a raw scraped location string."""
    if not raw:
        return (None, None)

    s = _WS_RE.sub(" ", str(raw)).strip().strip(",").strip()
    s = _COUNTRY_SUFFIX_RE.sub("", s).strip().strip(",").strip()
    low = s.lower()

    if low in _BLANK:
        return (None, None)
    if "remote" in low:
        return ("Remote", "Remote")

    # "<X> District" — always a region-only value, even when X is also a city.
    if _DISTRICT_WORD_RE.search(s):
        key = _DISTRICT_WORD_RE.sub("", low).strip()
        return (None, _DISTRICT_REGION.get(key))

    # A known city (Haifa / Jerusalem / Tel Aviv win here over the bare-region
    # reading below).
    if low in _CITIES:
        return _CITIES[low]

    # A bare region word with no "District" and no matching city.
    if low in _DISTRICT_REGION:
        return (None, _DISTRICT_REGION[low])

    # Unknown city — keep it as-is (country suffix already stripped), no region.
    return (s, None)
