"""Persistence for user-approved catalog aliases."""

from sqlalchemy import select

from database.models import ApprovedProductAlias
from database.session import session_scope


def find_approved_alias(
    normalized_alias: str, database_url: str | None = None
) -> ApprovedProductAlias | None:
    with session_scope(database_url) as session:
        return session.scalar(
            select(ApprovedProductAlias).where(
                ApprovedProductAlias.normalized_alias == normalized_alias
            )
        )


def save_approved_alias(
    *,
    normalized_alias: str,
    written_alias: str,
    catalog_row: int,
    official_product_name: str,
    database_url: str | None = None,
) -> ApprovedProductAlias:
    with session_scope(database_url) as session:
        existing = session.scalar(
            select(ApprovedProductAlias).where(
                ApprovedProductAlias.normalized_alias == normalized_alias
            )
        )
        if existing is None:
            existing = ApprovedProductAlias(
                normalized_alias=normalized_alias,
                written_alias=written_alias,
                catalog_row=catalog_row,
                official_product_name=official_product_name,
            )
            session.add(existing)
        else:
            existing.written_alias = written_alias
            existing.catalog_row = catalog_row
            existing.official_product_name = official_product_name
        session.flush()
        return existing
