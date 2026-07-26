"""Shared pharmaceutical text normalization used by matching and curated aliases."""

import re
import unicodedata

_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_EASTERN_ARABIC_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

_TERM_REPLACEMENTS = (
    (r"\b(?:micrograms?|microgrammes?|ميكروغرام|مايكروغرام|مكغ)\b", " mcg "),
    (r"\b(?:milligrams?|milli?grams?|مليغرام|مليجرام|ملغم|ملغ|مغم|مغ)\b", " mg "),
    (r"\b(?:grams?|غرام|جرام|غم)\b", " g "),
    (r"\b(?:millilitre|millilitres|milliliter|milliliters|مليلتر|ملليلتر|مل)\b", " ml "),
    (r"\b(?:international units?|i\.?\s*u\.?|units?|وحدات?|وحد[هة] دولي[هة])\b", " iu "),
    (r"\b(?:ampoules?|ampules?|amps?|امبولات?|امبول)\b", " amp "),
    (r"\b(?:vials?|فيالات?|فيال|قنين[هة])\b", " vial "),
    (r"\b(?:tablets?|tabs?|اقراص|قرص)\b", " tablet "),
    (r"\b(?:capsules?|caps?|كبسولات?|كبسول[هة])\b", " capsule "),
    (r"\b(?:suspensions?|susp|معلقات?|معلق)\b", " suspension "),
    (r"\b(?:injections?|inj|حقن[هة]?|للحقن)\b", " injection "),
    (r"\b(?:solutions?|soln|محلول)\b", " solution "),
    (r"\b(?:syrups?|شراب)\b", " syrup "),
    (r"\b(?:inhalation|inhal|استنشاق)\b", " inhal "),
    (r"\b(?:infusions?|infu|تسريب)\b", " infusion "),
    (r"\b(?:intravenous|i\.?\s*v\.?|وريدي)\b", " iv "),
    (r"\b(?:intramuscular|i\.?\s*m\.?|عضلي)\b", " im "),
    (r"\b(?:per\s+oral|orally|p\.?\s*o\.?|فموي|عن طريق الفم)\b", " po "),
)


def normalize_product_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.translate(_ARABIC_INDIC_DIGITS).translate(_EASTERN_ARABIC_DIGITS)
    value = value.replace("٫", ".").replace("٬", "")
    value = (
        value.replace("µg", " mcg ")
        .replace("μg", " mcg ")
        .replace("µ", " mcg ")
        .replace("μ", " mcg ")
    )
    value = re.sub(r"(?<=\d),(?=\d{3}\b)", "", value)
    value = re.sub(r"(?<=\d),(?=\d)", ".", value)
    value = value.lower()
    value = re.sub(r"[-‐‑–—]+", " ", value)
    value = re.sub(r"[\u064b-\u065f\u0670\u06d6-\u06edـ]", "", value)
    value = value.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي"}))
    value = re.sub(r"\b(?:نصف|نص|one\s+half|a\s+half|half)\b", " 0.5 ", value)
    value = re.sub(r"\b(?:ربع|one\s+quarter|a\s+quarter|quarter)\b", " 0.25 ", value)
    value = re.sub(
        r"(?<![\d.])(\d+)\s*/\s*(\d+)\s*(?=(?:mcg|mg|g|ml|iu|ميكرو|ملي|ملغ|مغ|غرام|جرام|غم)\b)",
        lambda match: f" {int(match.group(1)) / int(match.group(2)):g} ",
        value,
    )
    for pattern, replacement in _TERM_REPLACEMENTS:
        value = re.sub(pattern, replacement, value)
    # A slash before a unit is a formatting separator ("500 / mg"), not a ratio.
    value = re.sub(r"(?<=\d)\s*/\s*(?=(?:mg|mcg|g|ml|iu)\b)", " ", value)
    value = re.sub(r"(?<=\d)\s*(mg|mcg|g|ml|iu)\b", r" \1 ", value)
    value = re.sub(r"[^\w./%\s]", " ", value)
    value = re.sub(r"\s*/\s*", "/", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value
