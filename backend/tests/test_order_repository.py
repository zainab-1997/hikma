"""Tests for the order persistence repository and session/init layer.

Every test uses a fresh temporary SQLite file (via pytest's tmp_path) — none of them
touch the real backend/database/app.db.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from database.models import Order, OrderProduct
from database.repositories import order_repository
from database.repositories.order_repository import OrderInput, OrderProductInput
from database.session import init_db, session_scope


def _db_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path}/test.db"


def _product_input(**overrides) -> OrderProductInput:
    defaults = dict(
        written_product_name="Alpha",
        official_product_name="Alpha Tablet 50MG",
        worksheet_name="Sheet1",
        row_number=3,
        quantity=5,
        free_quantity=1,
    )
    defaults.update(overrides)
    return OrderProductInput(**defaults)


def _order_input(**overrides) -> OrderInput:
    defaults = dict(
        order_title="صيدلية العين - النجف",
        selected_price_type="pharmacy",
        selected_order_total=6000,
        generated_filename="order.xlsx",
        generated_file_id="order.xlsx",
        products=[_product_input()],
        customer_name="صيدلية العين",
        customer_type="pharmacy",
        governorate="النجف",
    )
    defaults.update(overrides)
    return OrderInput(**defaults)


# --- initialization -----------------------------------------------------------------------


def test_database_initialization_creates_tables(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)

    with session_scope(url) as session:
        # Both tables must exist and be queryable with zero rows.
        assert session.execute(select(func.count()).select_from(Order)).scalar_one() == 0
        assert session.execute(select(func.count()).select_from(OrderProduct)).scalar_one() == 0


def test_database_initialization_is_idempotent(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)
    init_db(database_url=url)  # must not raise on a second call


# --- header + product-line save -------------------------------------------------------------


def test_successful_order_header_save(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)

    with session_scope(url) as session:
        order = order_repository.create_order_with_products(session, _order_input())
        order_id = order.id

    with session_scope(url) as session:
        saved = session.get(Order, order_id)
        assert saved is not None
        assert saved.customer_name == "صيدلية العين"
        assert saved.order_title == "صيدلية العين - النجف"
        assert saved.selected_order_total == 6000


def test_successful_product_line_save(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)

    order_input = _order_input(
        products=[
            _product_input(written_product_name="Alpha", row_number=3, quantity=5),
            _product_input(written_product_name="Beta", row_number=4, quantity=10, free_quantity=0),
        ]
    )

    with session_scope(url) as session:
        order = order_repository.create_order_with_products(session, order_input)
        order_id = order.id

    with session_scope(url) as session:
        products = session.execute(
            select(OrderProduct).where(OrderProduct.order_id == order_id).order_by(OrderProduct.row_number)
        ).scalars().all()
        assert len(products) == 2
        assert products[0].written_product_name == "Alpha"
        assert products[0].quantity == 5
        assert products[1].written_product_name == "Beta"
        assert products[1].quantity == 10


def test_order_and_products_saved_in_one_transaction(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)

    with session_scope(url) as session:
        order = order_repository.create_order_with_products(session, _order_input())
        order_id = order.id

    with session_scope(url) as session:
        order_count = session.execute(select(func.count()).select_from(Order)).scalar_one()
        product_count = session.execute(
            select(func.count()).select_from(OrderProduct).where(OrderProduct.order_id == order_id)
        ).scalar_one()
        assert order_count == 1
        assert product_count == 1


def test_rollback_on_product_insert_failure(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)

    # row_number is a NOT NULL column — force a constraint violation on the product insert.
    bad_product = OrderProductInput(
        written_product_name="Alpha",
        official_product_name="Alpha Tablet 50MG",
        worksheet_name="Sheet1",
        row_number=None,
        quantity=5,
        free_quantity=0,
    )
    order_input = _order_input(products=[bad_product])

    with pytest.raises(IntegrityError):
        with session_scope(url) as session:
            order_repository.create_order_with_products(session, order_input)

    with session_scope(url) as session:
        assert session.execute(select(func.count()).select_from(Order)).scalar_one() == 0
        assert session.execute(select(func.count()).select_from(OrderProduct)).scalar_one() == 0


# --- order numbering -----------------------------------------------------------------------


def test_order_number_generated_correctly(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)

    with session_scope(url) as session:
        order = order_repository.create_order_with_products(session, _order_input())

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    assert order.order_number == f"HIK-{today}-0001"


def test_order_number_uniqueness_increments_sequentially(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)

    numbers = []
    for _ in range(3):
        with session_scope(url) as session:
            order = order_repository.create_order_with_products(session, _order_input())
            numbers.append(order.order_number)

    assert len(set(numbers)) == 3
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    assert numbers == [f"HIK-{today}-000{i}" for i in (1, 2, 3)]


def test_order_number_uses_utc_date(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)

    reference = datetime(2026, 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
    with session_scope(url) as session:
        number = order_repository.generate_order_number(session, reference_date=reference)

    assert number == "HIK-20251231-0001"


# --- timestamps -----------------------------------------------------------------------------


def test_utc_timestamps_are_stored(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)

    before = datetime.now(timezone.utc)
    with session_scope(url) as session:
        order = order_repository.create_order_with_products(session, _order_input())
    after = datetime.now(timezone.utc)

    assert order.created_at.tzinfo is not None
    assert before - timedelta(seconds=5) <= order.created_at <= after + timedelta(seconds=5)


# --- idempotency lookup ---------------------------------------------------------------------


def test_find_order_by_client_request_id(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)

    order_input = _order_input(client_request_id="req-abc-123")
    with session_scope(url) as session:
        created = order_repository.create_order_with_products(session, order_input)
        created_id = created.id

    with session_scope(url) as session:
        found = order_repository.find_order_by_client_request_id(session, "req-abc-123")
        assert found is not None
        assert found.id == created_id

        assert order_repository.find_order_by_client_request_id(session, "does-not-exist") is None


# --- listing, filtering, pagination ----------------------------------------------------------


def _seed_orders(url):
    with session_scope(url) as session:
        order_repository.create_order_with_products(
            session,
            _order_input(customer_name="صيدلية العين", governorate="النجف", selected_price_type="pharmacy"),
        )
    with session_scope(url) as session:
        order_repository.create_order_with_products(
            session,
            _order_input(customer_name="مذخر الوافي", governorate="بغداد", selected_price_type="drug_store"),
        )
    with session_scope(url) as session:
        order_repository.create_order_with_products(
            session,
            _order_input(customer_name="صيدلية بغداد", governorate="بغداد", selected_price_type="pharmacy"),
        )


def test_list_orders_returns_all_by_default(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)
    _seed_orders(url)

    with session_scope(url) as session:
        orders, total = order_repository.list_orders(session)

    assert total == 3
    assert len(orders) == 3


def test_filtering_by_governorate(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)
    _seed_orders(url)

    with session_scope(url) as session:
        orders, total = order_repository.list_orders(session, governorate="بغداد")

    assert total == 2
    assert all(order.governorate == "بغداد" for order in orders)


def test_filtering_by_customer_name(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)
    _seed_orders(url)

    with session_scope(url) as session:
        orders, total = order_repository.list_orders(session, customer_name="العين")

    assert total == 1
    assert orders[0].customer_name == "صيدلية العين"


def test_filtering_by_price_type(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)
    _seed_orders(url)

    with session_scope(url) as session:
        orders, total = order_repository.list_orders(session, price_type="drug_store")

    assert total == 1
    assert orders[0].selected_price_type == "drug_store"


def test_filtering_by_date_range(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)
    _seed_orders(url)

    future_start = datetime.now(timezone.utc) + timedelta(days=1)
    with session_scope(url) as session:
        orders, total = order_repository.list_orders(session, date_from=future_start)
    assert total == 0

    past_start = datetime.now(timezone.utc) - timedelta(days=1)
    with session_scope(url) as session:
        orders, total = order_repository.list_orders(session, date_from=past_start)
    assert total == 3


def test_pagination(tmp_path):
    url = _db_url(tmp_path)
    init_db(database_url=url)
    _seed_orders(url)

    with session_scope(url) as session:
        first_page, total = order_repository.list_orders(session, limit=2, offset=0)
        second_page, _ = order_repository.list_orders(session, limit=2, offset=2)

    assert total == 3
    assert len(first_page) == 2
    assert len(second_page) == 1
    assert {o.id for o in first_page}.isdisjoint({o.id for o in second_page})
