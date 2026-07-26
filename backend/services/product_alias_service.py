"""Loads curated product-name aliases from backend/data/product_aliases.json.

Aliases are a small, human-curated correction layer for cases the deterministic
string/parenthetical-alias matching in product_matching_service can't bridge on its own —
most notably Arabic brand names that don't share a script with the English catalog, so
plain string-similarity scoring gives them near-zero overlap no matter how obviously a
human would recognize the product.

Two kinds of entries are supported, and the distinction matters:

- `exact_aliases`: a full written phrase that resolves to exactly ONE catalog row, e.g.
  "فانكو 500" -> row 14. Only add these when the phrase is unambiguous on its own.
- `brand_aliases`: a bare brand token (e.g. "فانكو" -> "vanco") that gets substituted
  into the written text before the normal scoring pipeline runs. This does NOT force a
  match — if the brand exists at multiple strengths in the catalog (as VANCO does), the
  substituted text still scores against every catalog row and the normal
  ambiguity/candidate logic decides. This is how "plain فانكو" correctly stays
  ambiguous instead of guessing a strength.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from utils.text_normalize import normalize_product_text

logger = logging.getLogger(__name__)

DEFAULT_ALIASES_PATH = Path(__file__).resolve().parent.parent / "data" / "product_aliases.json"


@dataclass(frozen=True)
class AliasIndex:
    exact: dict[str, int] = field(default_factory=dict)
    brand: dict[str, str] = field(default_factory=dict)


def load_alias_index(path: Path | str = DEFAULT_ALIASES_PATH) -> AliasIndex:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return AliasIndex()
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to load product aliases from %s: %s", path, exc)
        return AliasIndex()

    exact: dict[str, int] = {}
    for entry in raw.get("exact_aliases", []):
        written = entry.get("written")
        row = entry.get("row")
        if written and isinstance(row, int):
            exact[normalize_product_text(written)] = row

    brand: dict[str, str] = {}
    for entry in raw.get("brand_aliases", []):
        written = entry.get("written")
        brand_text = entry.get("brand")
        if written and brand_text:
            brand[normalize_product_text(written)] = normalize_product_text(brand_text)

    return AliasIndex(exact=exact, brand=brand)
