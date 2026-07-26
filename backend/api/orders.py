"""HTTP routes for WhatsApp order parsing, business rules, matching, Excel generation,
and order history."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from excel.catalog_reader import CatalogUnavailableError
from excel.order_writer import ExcelGenerationError
from models.email_models import EmailDeliveryDetail, EmailDeliverySummary, SendOrderEmailRequest, SendOrderEmailResponse
from models.generate_order_models import GenerateOrderRequest, GeneratedOrderResponse
from models.matched_order_models import MatchedOrderResponse
from models.order_history_models import OrderDetail, OrderListResponse
from models.order_models import ParseOrderRequest, ParsedOrderResponse
from models.review_order_models import ApplyRulesRequest, ReviewOrderResponse
from services.ai_parser_service import OrderParsingError, parse_whatsapp_order
from services.business_rules_service import apply_business_rules
from services.email_delivery_service import (
    get_email_delivery_detail,
    list_email_deliveries,
    send_order_email,
)
from services.email_errors import EmailDeliveryError
from services.excel_generation_service import resolve_generated_file_path
from services.order_persistence_service import (
    generate_and_persist_order,
    get_order_detail,
    get_order_generated_file_id,
    list_order_summaries,
)
from services.product_matching_service import match_order_products

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orders", tags=["orders"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/parse", response_model=ParsedOrderResponse)
def parse_order(request: ParseOrderRequest) -> ParsedOrderResponse:
    try:
        return parse_whatsapp_order(request.message)
    except OrderParsingError as exc:
        logger.error("Order parsing failed: %s", exc)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected error while parsing an order message.")
        raise HTTPException(
            status_code=500,
            detail="Unexpected error while parsing the order.",
        )


@router.post("/apply-rules", response_model=ReviewOrderResponse)
def apply_rules(request: ApplyRulesRequest) -> ReviewOrderResponse:
    try:
        return apply_business_rules(request)
    except Exception:
        logger.exception("Unexpected error while applying business rules.")
        raise HTTPException(
            status_code=500,
            detail="Unexpected error while applying business rules.",
        )


@router.post("/match-products", response_model=MatchedOrderResponse)
def match_products(request: ReviewOrderResponse) -> MatchedOrderResponse:
    try:
        return match_order_products(request)
    except CatalogUnavailableError as exc:
        logger.error("Product catalog unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="The product catalog is currently unavailable.",
        ) from exc
    except Exception:
        logger.exception("Unexpected error while matching products.")
        raise HTTPException(
            status_code=500,
            detail="Unexpected error while matching products.",
        )


@router.post("/generate-excel", response_model=GeneratedOrderResponse)
def generate_excel(request: GenerateOrderRequest) -> GeneratedOrderResponse:
    try:
        return generate_and_persist_order(request)
    except ExcelGenerationError as exc:
        logger.error("Excel generation/persistence failed: %s", exc)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected error while generating the Excel order.")
        raise HTTPException(
            status_code=500,
            detail="Unexpected error while generating the Excel order.",
        )


@router.get("", response_model=OrderListResponse)
def list_orders(
    customer_name: str | None = Query(default=None),
    governorate: str | None = Query(default=None),
    customer_type: str | None = Query(default=None),
    price_type: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> OrderListResponse:
    try:
        return list_order_summaries(
            customer_name=customer_name,
            governorate=governorate,
            customer_type=customer_type,
            price_type=price_type,
            date_from=date_from,
            date_to=date_to,
            search=search,
            limit=limit,
            offset=offset,
        )
    except Exception:
        logger.exception("Unexpected error while listing orders.")
        raise HTTPException(status_code=500, detail="Unexpected error while listing orders.")


@router.get("/download/{file_id}")
def download_generated_order(file_id: str) -> FileResponse:
    try:
        file_path = resolve_generated_file_path(file_id)
    except ExcelGenerationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="The requested file was not found.")

    return FileResponse(path=file_path, media_type=XLSX_MEDIA_TYPE, filename=file_path.name)


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(order_id: str) -> OrderDetail:
    try:
        detail = get_order_detail(order_id)
    except Exception:
        logger.exception("Unexpected error while loading order %s.", order_id)
        raise HTTPException(status_code=500, detail="Unexpected error while loading the order.")

    if detail is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return detail


@router.get("/{order_id}/download")
def download_order_file(order_id: str) -> FileResponse:
    try:
        file_id = get_order_generated_file_id(order_id)
    except Exception:
        logger.exception("Unexpected error while loading order %s for download.", order_id)
        raise HTTPException(status_code=500, detail="Unexpected error while loading the order.")

    if file_id is None:
        raise HTTPException(status_code=404, detail="Order not found.")

    try:
        file_path = resolve_generated_file_path(file_id)
    except ExcelGenerationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="The generated file for this order was not found.")

    return FileResponse(path=file_path, media_type=XLSX_MEDIA_TYPE, filename=file_path.name)


@router.post("/{order_id}/send-email", response_model=SendOrderEmailResponse)
def send_order_email_route(order_id: str, request: SendOrderEmailRequest) -> SendOrderEmailResponse:
    try:
        return send_order_email(order_id, request)
    except EmailDeliveryError as exc:
        logger.error("Email send request rejected for order %s: %s", order_id, exc)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected error while sending email for order %s.", order_id)
        raise HTTPException(status_code=500, detail="Unexpected error while sending the order email.")


@router.get("/{order_id}/emails", response_model=list[EmailDeliverySummary])
def list_order_emails(order_id: str) -> list[EmailDeliverySummary]:
    try:
        return list_email_deliveries(order_id)
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected error while listing email deliveries for order %s.", order_id)
        raise HTTPException(status_code=500, detail="Unexpected error while listing email deliveries.")


@router.get("/{order_id}/emails/{delivery_id}", response_model=EmailDeliveryDetail)
def get_order_email(order_id: str, delivery_id: str) -> EmailDeliveryDetail:
    try:
        detail = get_email_delivery_detail(order_id, delivery_id)
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected error while loading email delivery %s for order %s.", delivery_id, order_id)
        raise HTTPException(status_code=500, detail="Unexpected error while loading the email delivery.")

    if detail is None:
        raise HTTPException(status_code=404, detail="Email delivery not found.")
    return detail
