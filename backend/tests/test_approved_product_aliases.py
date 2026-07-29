from database.repositories.product_alias_repository import (
    find_approved_alias,
    save_approved_alias,
)
from database.session import init_db


def test_approved_alias_is_persisted_in_sqlite_and_can_be_updated(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'aliases.db'}"
    init_db(database_url)

    save_approved_alias(
        normalized_alias="اسم عربي",
        written_alias="اسم عربي",
        catalog_row=3,
        official_product_name="PRODUCT A",
        database_url=database_url,
    )
    stored = find_approved_alias("اسم عربي", database_url)
    assert stored is not None
    assert stored.catalog_row == 3

    save_approved_alias(
        normalized_alias="اسم عربي",
        written_alias="إسم عربي",
        catalog_row=4,
        official_product_name="PRODUCT B",
        database_url=database_url,
    )
    updated = find_approved_alias("اسم عربي", database_url)
    assert updated is not None
    assert updated.catalog_row == 4
    assert updated.official_product_name == "PRODUCT B"
