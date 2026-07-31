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


_LOCATION_LABEL = re.compile(
    r"^(?:المحافظ[هة]|محافظ[هة]|المدين[هة]|مدين[هة]|governorate|province|city)\s*[:：]?\s*",
    re.IGNORECASE,
)
_AREA_LABEL = re.compile(
    r"^(?:المنطق[هة]|منطق[هة]|الحي|حي|القضاء|قضاء|الناحي[هة]|ناحي[هة]|"
    r"area|district|neighbou?rhood)\s*[:：]?\s*(.+)$",
    re.IGNORECASE,
)
_CUSTOMER_HEADER = re.compile(
    r"(?:صيدلي[هة]|مستشفى|مذخر|مخزن\s+ادوي[هة]|مكتب\s+علمي|"
    r"pharmacy|hospital|drug\s*store|scientific\s+office|warehouse)",
    re.IGNORECASE,
)
_ORDERISH_LINE = re.compile(
    r"\d|[٠-٩۰-۹]|(?:qty|quantity|عدد|كمي[هة]|free|bonus|مجاني)|[×=*+]",
    re.IGNORECASE,
)
_FIELD_LABELS = (
    r"المحافظ[هة]|محافظ[هة]|المدين[هة]|مدين[هة]|المنطق[هة]|منطق[هة]|"
    r"الحي|حي|القضاء|قضاء|الناحي[هة]|ناحي[هة]|العنوان|عنوان|الموقع|موقع|"
    r"governorate|province|city|area|district|neighbou?rhood|address|location"
)


def _label_value(text: str, labels: str) -> str | None:
    """Read a labelled value without altering the original WhatsApp text."""
    match = re.search(
        rf"(?:^|[\n,،;؛|])\s*(?:{labels})\s*[:：=\-/]?\s*"
        rf"(.+?)(?=\s+(?:{_FIELD_LABELS})\s*[:：=\-/]?|[\n,،;؛|]|$)",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _matched_alias_span(line: str) -> tuple[int, int] | None:
    """Locate the first known location alias in a normalized line."""
    normalized = _key(line)
    best: tuple[int, int] | None = None
    for _location, aliases in _ENTRIES:
        for alias in aliases:
            alias_key = _key(alias)
            match = re.search(rf"(?<!\w){re.escape(alias_key)}(?!\w)", normalized)
            if match and (best is None or match.start() < best[0]):
                best = match.span()
    return best


def _remainder_after_location_alias(line: str) -> str | None:
    """Return text following a location alias while retaining the sender's spelling."""
    best: tuple[int, int] | None = None
    for _location, aliases in _ENTRIES:
        for alias in aliases:
            match = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", line, re.IGNORECASE)
            if match and (best is None or match.start() < best[0]):
                best = match.span()
    if best is None:
        return None
    return line[best[1]:].strip(" /\\-–—,:：،")


def extract_iraqi_customer_location(
    text: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Extract governorate, city and structurally stated area.

    Governorate/city recognition uses the canonical location registry above. Area names
    are deliberately not enumerated: they are captured from labels, separators, or the
    header line immediately following a standalone location.
    """
    if not text:
        return None, None, None

    governorate_value = _label_value(text, r"المحافظ[هة]|محافظ[هة]|governorate|province")
    city_value = _label_value(text, r"المدين[هة]|مدين[هة]|city")
    area_value = _label_value(
        text,
        r"المنطق[هة]|منطق[هة]|الحي|حي|القضاء|قضاء|الناحي[هة]|ناحي[هة]|"
        r"area|district|neighbou?rhood",
    )
    named_area = re.search(
        r"(?:^|[\n,،;؛|])\s*((?:الحي|حي|القضاء|قضاء|الناحي[هة]|ناحي[هة])"
        r"\s*[:：]?\s*[^\n,،;؛|]+)",
        text,
        re.IGNORECASE,
    )
    if named_area:
        area_value = named_area.group(1).strip()
    address_value = _label_value(text, r"العنوان|عنوان|الموقع|موقع|address|location")

    governorate, city = extract_iraqi_location(governorate_value or text)
    if governorate is None:
        governorate, city = extract_iraqi_location(address_value)
    if city_value:
        city_governorate, explicit_city = extract_iraqi_location(city_value)
        if governorate is None:
            governorate = city_governorate
        city = explicit_city or city_governorate or city_value

    area: str | None = area_value
    if not governorate:
        # An explicitly labelled area is still useful even when no governorate exists.
        return None, city, area

    lines = [re.sub(r"\s+", " ", line).strip(" \t,،;؛") for line in text.splitlines()]
    lines = [line for line in lines if line]

    for index, raw_line in enumerate(lines):
        if area:
            break
        labelled_area = _AREA_LABEL.match(_key(raw_line))
        if labelled_area:
            area = labelled_area.group(1).strip()
            break

        if extract_iraqi_location(raw_line)[0] != governorate:
            continue

        unlabelled_line = _LOCATION_LABEL.sub("", raw_line)
        normalized_line = _key(unlabelled_line)
        alias_span = _matched_alias_span(normalized_line)
        if alias_span:
            remainder = _remainder_after_location_alias(unlabelled_line)
            if remainder and not _ORDERISH_LINE.search(remainder):
                area = remainder
                break

        # A standalone location in a customer header may be followed by an area line.
        location_only = _LOCATION_LABEL.sub("", raw_line)
        if _matched_alias_span(location_only) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if (
                not extract_iraqi_location(next_line)[0]
                and not _CUSTOMER_HEADER.search(_key(next_line))
                and not _ORDERISH_LINE.search(next_line)
            ):
                area = next_line.strip()
                break

    # "مدينة بغداد" explicitly describes the city, even when governorate and city share
    # a name. Do not infer this from a bare governorate mention.
    if city is None:
        for line in lines:
            if re.match(r"^(?:المدين[هة]|مدين[هة]|city)\b", _key(line), re.IGNORECASE):
                line_governorate, line_city = extract_iraqi_location(line)
                if line_governorate:
                    city = line_city or line_governorate
                    break

    return governorate, city, area


def normalize_governorate(value: str | None) -> str | None:
    governorate, _city = extract_iraqi_location(value)
    return governorate or ((value or "").strip() or None)
