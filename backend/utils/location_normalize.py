"""Deterministic Iraqi governorate/city extraction for Arabic and English text."""

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class IraqiLocation:
    governorate_ar: str
    governorate_en: str
    city_ar: str | None = None
    city_en: str | None = None


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    value = re.sub(r"[\u064b-\u065f\u0670\u06d6-\u06edـ]", "", value)
    value = value.translate(
        str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه"})
    )
    value = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


_ENTRIES: tuple[tuple[IraqiLocation, tuple[str, ...]], ...] = (
    (IraqiLocation("بغداد", "Baghdad"), ("بغداد", "baghdad")),
    (IraqiLocation("البصرة", "Basra"), ("البصرة", "بصره", "basra", "al basra")),
    (IraqiLocation("نينوى", "Nineveh"), ("نينوى", "نينوه", "nineveh", "naynawa")),
    (IraqiLocation("نينوى", "Nineveh", "الموصل", "Mosul"), ("الموصل", "موصل", "mosul")),
    (IraqiLocation("كربلاء", "Karbala"), ("كربلاء", "karbala")),
    (IraqiLocation("النجف", "Najaf"), ("النجف", "نجف", "najaf")),
    (IraqiLocation("أربيل", "Erbil"), ("أربيل", "اربيل", "erbil", "hawler")),
    (IraqiLocation("السليمانية", "Sulaymaniyah"), ("السليمانية", "سليمانيه", "sulaymaniyah", "sulaimaniyah")),
    (IraqiLocation("كركوك", "Kirkuk"), ("كركوك", "kirkuk")),
    (IraqiLocation("الأنبار", "Anbar"), ("الأنبار", "الانبار", "انبار", "anbar", "al anbar")),
    (IraqiLocation("ديالى", "Diyala"), ("ديالى", "دياله", "diyala")),
    (IraqiLocation("واسط", "Wasit"), ("واسط", "wasit")),
    (IraqiLocation("بابل", "Babil"), ("بابل", "babil", "babylon")),
    (IraqiLocation("الديوانية", "Diwaniyah"), ("الديوانية", "ديوانيه", "diwaniyah", "diwaniya")),
    (IraqiLocation("المثنى", "Muthanna"), ("المثنى", "مثنى", "muthanna")),
    (IraqiLocation("ميسان", "Maysan"), ("ميسان", "maysan", "missan")),
    (IraqiLocation("ذي قار", "Dhi Qar"), ("ذي قار", "ذيقار", "dhi qar", "thi qar")),
    (IraqiLocation("صلاح الدين", "Salah Al-Din"), ("صلاح الدين", "salah al din", "salahuddin")),
    (IraqiLocation("دهوك", "Duhok"), ("دهوك", "dohuk", "duhok")),
)


def extract_iraqi_location(text: str | None) -> tuple[str | None, str | None]:
    """Return canonical governorate/city in the script used by the input."""
    if not text:
        return None, None
    normalized = f" {_key(text)} "
    arabic = bool(re.search(r"[\u0600-\u06ff]", text))
    matches: list[tuple[int, IraqiLocation]] = []
    for location, aliases in _ENTRIES:
        for alias in aliases:
            alias_key = _key(alias)
            match = re.search(rf"(?<!\w){re.escape(alias_key)}(?!\w)", normalized)
            if match:
                matches.append((match.start(), location))
                break
    if not matches:
        return None, None
    location = min(matches, key=lambda item: item[0])[1]
    return (
        location.governorate_ar if arabic else location.governorate_en,
        location.city_ar if arabic else location.city_en,
    )


def normalize_governorate(value: str | None) -> str | None:
    governorate, _city = extract_iraqi_location(value)
    return governorate or ((value or "").strip() or None)
