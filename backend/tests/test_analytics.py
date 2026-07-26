"""Analytics tests use only a temporary SQLite database."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from database.models import EmailDelivery, Order, OrderProduct
from database.repositories import analytics_repository as repository
from database.repositories.analytics_repository import AnalyticsFilters
from database.session import get_session_factory, init_db, session_scope
from main import app
from services import analytics_service


UTC = timezone.utc


def _dt(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 7, day, hour, 0, tzinfo=UTC)


@pytest.fixture
def analytics_db(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'analytics.db'}"
    init_db(url)
    factory = get_session_factory(url)

    def add_order(
        session, oid, day, customer, customer_type, governorate, price_type, total, products
    ):
        order = Order(
            id=oid,
            order_number=f"HIK-202607{day:02d}-{oid}",
            customer_name=customer,
            customer_type=customer_type,
            governorate=governorate,
            order_title="Test",
            selected_price_type=price_type,
            selected_order_total=total,
            generated_filename="safe.xlsx",
            generated_file_id="safe.xlsx",
            created_at=_dt(day),
            updated_at=_dt(day),
        )
        session.add(order)
        for index, (name, quantity, free) in enumerate(products):
            session.add(
                OrderProduct(
                    id=f"{oid}-p{index}",
                    order_id=oid,
                    written_product_name=name,
                    official_product_name=name,
                    worksheet_name="Sheet",
                    row_number=index + 1,
                    quantity=quantity,
                    free_quantity=free,
                    created_at=_dt(day),
                )
            )

    with factory() as session:
        add_order(session, "o1", 1, "Alpha", "pharmacy", "Najaf", "pharmacy", 1000, [("Prod A", 10, 1)])
        add_order(
            session, "o2", 2, "Alpha", "pharmacy", "Najaf", "pharmacy", 3000, [("Prod A", 20, 2), ("Prod B", 5, 0)]
        )
        add_order(session, "o3", 8, "Beta", "drug_store", "Baghdad", "drug_store", 6000, [("Prod B", 30, 3)])
        add_order(session, "o4", 31, None, None, None, "pharmacy", 0, [("Prod C", 2, 0)])
        for eid, oid, status, day in [
            ("e1", "o1", "sent", 1),
            ("e2", "o2", "failed", 2),
            ("e3", "o2", "pending", 2),
            ("e4", "o3", "sending", 8),
        ]:
            session.add(
                EmailDelivery(
                    id=eid,
                    order_id=oid,
                    email_request_id=eid,
                    attempt_number=1,
                    status=status,
                    to_addresses="[]",
                    cc_addresses="[]",
                    subject="Safe",
                    created_at=_dt(day),
                )
            )
        session.commit()

    @contextmanager
    def temporary_scope():
        with session_scope(url) as session:
            yield session

    monkeypatch.setattr(analytics_service, "session_scope", temporary_scope)
    return url


def test_empty_database_overview_and_no_division_by_zero(tmp_path):
    url = f"sqlite:///{tmp_path / 'empty.db'}"
    init_db(url)
    with session_scope(url) as session:
        data = repository.overview(session, AnalyticsFilters())
        email = repository.email_deliveries(session, AnalyticsFilters())
    assert data["total_orders"] == data["total_sales_value"] == data["total_ordered_quantity"] == 0
    assert email["total_attempts"] == 0


def test_overview_totals_uniques_and_email_counts(analytics_db):
    result = analytics_service.get_overview(AnalyticsFilters())
    assert result.total_orders == 4
    assert result.total_sales_value == 10000
    assert result.total_ordered_quantity == 67
    assert result.total_free_quantity == 6
    assert result.average_order_value == 2500
    assert result.unique_customers == 2
    assert result.unique_governorates == 2
    assert result.sent_email_count == result.failed_email_count == 1


def test_governorates_group_missing_as_unknown(analytics_db):
    rows = analytics_service.get_by_governorate(AnalyticsFilters())
    assert [(r.governorate, r.order_count) for r in rows] == [
        ("Baghdad", 1), ("Najaf", 2), ("Unknown", 1)
    ]


def test_daily_weekly_and_monthly_grouping(analytics_db):
    daily = analytics_service.get_sales_over_time(AnalyticsFilters(), "daily")
    weekly = analytics_service.get_sales_over_time(AnalyticsFilters(), "weekly")
    monthly = analytics_service.get_sales_over_time(AnalyticsFilters(), "monthly")
    assert [r.period for r in daily] == ["2026-07-01", "2026-07-02", "2026-07-08", "2026-07-31"]
    assert [(r.period, r.order_count) for r in weekly] == [
        ("2026-06-29", 2), ("2026-07-06", 1), ("2026-07-27", 1)
    ]
    assert [(r.period, r.sales_total) for r in monthly] == [("2026-07", 10000)]


def test_filters_for_dates_customer_price_governorate_and_product(analytics_db):
    assert analytics_service.get_overview(AnalyticsFilters(date_from=_dt(8, 0))).total_orders == 2
    assert analytics_service.get_overview(
        AnalyticsFilters(date_to_exclusive=datetime(2026, 7, 3, tzinfo=UTC))
    ).total_orders == 2
    assert analytics_service.get_overview(AnalyticsFilters(customer_type="drug_store")).total_sales_value == 6000
    assert analytics_service.get_overview(AnalyticsFilters(selected_price_type="pharmacy")).total_orders == 3
    assert analytics_service.get_overview(AnalyticsFilters(governorate="Najaf")).total_orders == 2
    assert analytics_service.get_overview(AnalyticsFilters(product_name="Prod C")).total_orders == 1


def test_customer_totals_pagination_and_sort(analytics_db):
    result = analytics_service.get_by_customer(AnalyticsFilters(), 1, 0, "total_sales", True)
    assert result.total == 2
    assert result.items[0].customer_name == "Beta"
    alpha = analytics_service.get_by_customer(AnalyticsFilters(customer_name="Alpha"), 50, 0, "customer_name", False)
    assert alpha.items[0].order_count == 2
    assert alpha.items[0].total_sales == 4000
    assert alpha.items[0].average_order_value == 2000


def test_product_quantities_unique_customers_and_no_revenue(analytics_db):
    result = analytics_service.get_products(AnalyticsFilters(), 50, 0, "total_quantity", True)
    product_a = next(item for item in result.items if item.official_product_name == "Prod A")
    assert (product_a.total_quantity, product_a.total_free_quantity, product_a.order_count) == (30, 3, 2)
    assert product_a.unique_customer_count == 1
    assert result.sales_value_available is False
    assert "unit price" in result.sales_value_limitation
    assert "sales_total" not in product_a.model_dump()


def test_price_and_customer_type_splits(analytics_db):
    prices = {row.price_type: row for row in analytics_service.get_price_types(AnalyticsFilters())}
    assert prices["pharmacy"].sales_total == 4000
    assert prices["pharmacy"].percentage_of_total_sales == 40
    customer_types = {row.customer_type: row for row in analytics_service.get_customer_types(AnalyticsFilters())}
    assert customer_types["pharmacy"].order_count == 2
    assert customer_types["Unknown"].order_count == 1


def test_email_delivery_analytics(analytics_db):
    result = analytics_service.get_email_deliveries(AnalyticsFilters())
    assert (result.sent, result.failed, result.pending, result.sending, result.total_attempts) == (1, 1, 1, 1, 4)
    assert result.success_rate == 25
    assert result.latest_failure_time is not None


def test_filter_options(analytics_db):
    result = analytics_service.get_filter_options()
    assert result.governorates == ["Baghdad", "Najaf"]
    assert result.price_types == ["drug_store", "pharmacy"]
    assert (result.minimum_order_date, result.maximum_order_date) == ("2026-07-01", "2026-07-31")


def test_api_date_to_includes_complete_utc_day_and_invalid_range_is_safe(analytics_db):
    client = TestClient(app)
    response = client.get("/api/analytics/overview", params={"date_to": "2026-07-02"})
    assert response.status_code == 200
    assert response.json()["total_orders"] == 2
    invalid = client.get(
        "/api/analytics/overview", params={"date_from": "2026-07-03", "date_to": "2026-07-02"}
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "date_from must be on or before date_to."
    assert "Traceback" not in invalid.text


def test_api_rejects_invalid_granularity_sort_and_direction(analytics_db):
    client = TestClient(app)
    assert client.get("/api/analytics/sales-over-time?granularity=yearly").status_code == 422
    assert client.get("/api/analytics/products?sort_by=revenue").status_code == 422
    assert client.get("/api/analytics/by-customer?sort_direction=sideways").status_code == 422


def test_api_limit_maximum_and_response_exposes_no_sensitive_fields(analytics_db):
    client = TestClient(app)
    assert client.get("/api/analytics/products?limit=201").status_code == 422
    response = client.get("/api/analytics/products")
    assert response.status_code == 200
    for forbidden in ("/Users/", "SELECT ", "source_message", "generated_filename", "smtp"):
        assert forbidden not in response.text


def test_source_workbook_hash_is_unchanged():
    import hashlib

    workbook = Path(__file__).parents[1] / "templates" / "Hikma orders.xlsx"
    assert hashlib.sha256(workbook.read_bytes()).hexdigest() == (
        "730edb4229048a7b7ff6b593749e7b507cfd547936fe7b306637869636f119c8"
    )
