from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from django.utils import timezone

from central.models import Product, Warehouse
from apps.inventory.models import (
    Batch,
    InventoryAlert,
    ProductPolicy,
    Stock,
    StockMovement,
)


STOCK_STATUSES = ["EMPTY", "ALMOST_OUT", "GOOD", "FULL"]
ALERT_TYPES = ["LOW_STOCK", "OUT_OF_STOCK", "EXPIRY"]
MOVEMENT_TYPES = ["IN", "OUT", "ADJUSTMENT", "RETURN"]


class InventoryOverviewService:
    @staticmethod
    def summary(company, *, warehouse_id=None, low_stock_limit=10):
        today = timezone.localdate()

        products = Product.objects.filter(company=company)
        warehouses = Warehouse.objects.filter(company=company)
        stocks = Stock.objects.filter(product__company=company)
        batches = Batch.objects.filter(product__company=company)
        alerts = InventoryAlert.objects.filter(product__company=company)
        movements = StockMovement.objects.filter(warehouse__company=company)
        policies = ProductPolicy.objects.filter(product__company=company)

        if warehouse_id:
            warehouses = warehouses.filter(id=warehouse_id)
            stocks = stocks.filter(warehouse_id=warehouse_id)
            batches = batches.filter(warehouse_id=warehouse_id)
            alerts = alerts.filter(warehouse_id=warehouse_id)
            movements = movements.filter(warehouse_id=warehouse_id)
            policies = policies.filter(warehouse_id=warehouse_id)

        active_products = products.filter(is_active=True)
        active_product_ids_with_policy = policies.filter(is_active=True).values(
            "product_id"
        )
        products_without_policy = active_products.exclude(
            id__in=active_product_ids_with_policy
        )

        return {
            "as_of_date": today,
            "warehouse_id": warehouse_id,
            "total_active_products": active_products.count(),
            "total_warehouses": warehouses.count(),
            "stock_status_counts": InventoryOverviewService._count_by_field(
                stocks,
                "status",
                STOCK_STATUSES,
            ),
            "open_alert_counts_by_type": InventoryOverviewService._count_by_field(
                alerts.filter(status="OPEN"),
                "alert_type",
                ALERT_TYPES,
            ),
            "batches_expiring": {
                "within_7_days": InventoryOverviewService._expiring_batch_summary(
                    batches, today, 7
                ),
                "within_14_days": InventoryOverviewService._expiring_batch_summary(
                    batches, today, 14
                ),
                "within_30_days": InventoryOverviewService._expiring_batch_summary(
                    batches, today, 30
                ),
            },
            "expired_batches_with_quantity": InventoryOverviewService._expired_batch_summary(
                batches, today
            ),
            "stock_movement_counts_by_type": InventoryOverviewService._count_by_field(
                movements,
                "movement_type",
                MOVEMENT_TYPES,
            ),
            "top_low_stock_products": InventoryOverviewService._top_low_stock_products(
                stocks,
                limit=low_stock_limit,
            ),
            "products_without_active_reorder_policy": {
                "count": products_without_policy.count(),
                "products": list(
                    products_without_policy.order_by("name").values(
                        "id",
                        "sku",
                        "name",
                        "category",
                        "unit_of_measure",
                    )[:low_stock_limit]
                ),
            },
        }

    @staticmethod
    def movement_trends(
        company,
        *,
        date_from=None,
        date_to=None,
        warehouse_id=None,
        interval="month",
    ):
        movements = StockMovement.objects.filter(warehouse__company=company)

        if warehouse_id:
            movements = movements.filter(warehouse_id=warehouse_id)
        if date_from:
            movements = movements.filter(created_at__date__gte=date_from)
        if date_to:
            movements = movements.filter(created_at__date__lte=date_to)

        trunc = InventoryOverviewService._trunc_function(interval)

        return {
            "date_from": date_from,
            "date_to": date_to,
            "warehouse_id": warehouse_id,
            "interval": interval,
            "inbound": InventoryOverviewService._movement_period_rows(
                movements.filter(movement_type="IN"),
                trunc("created_at"),
            ),
            "outbound": InventoryOverviewService._movement_period_rows(
                movements.filter(movement_type="OUT"),
                trunc("created_at"),
            ),
            "adjustments": InventoryOverviewService._movement_period_rows(
                movements.filter(movement_type="ADJUSTMENT"),
                trunc("created_at"),
            ),
            "returns": InventoryOverviewService._movement_period_rows(
                movements.filter(movement_type="RETURN"),
                trunc("created_at"),
            ),
        }

    @staticmethod
    def _count_by_field(queryset, field_name, expected_values):
        counts = {
            row[field_name]: row["count"]
            for row in queryset.values(field_name).annotate(count=Count("id"))
        }
        return {value: counts.get(value, 0) for value in expected_values}

    @staticmethod
    def _expiring_batch_summary(batches, today, days):
        rows = batches.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=days),
            quantity__gt=0,
        )
        return {
            "count": rows.count(),
            "quantity": rows.aggregate(total=Sum("quantity"))["total"] or Decimal("0"),
        }

    @staticmethod
    def _expired_batch_summary(batches, today):
        rows = batches.filter(expiry_date__lt=today, quantity__gt=0)
        return {
            "count": rows.count(),
            "quantity": rows.aggregate(total=Sum("quantity"))["total"] or Decimal("0"),
        }

    @staticmethod
    def _top_low_stock_products(stocks, *, limit):
        active_policy = ProductPolicy.objects.filter(
            product_id=OuterRef("product_id"),
            warehouse_id=OuterRef("warehouse_id"),
            is_active=True,
        )
        rows = (
            stocks.annotate(
                min_stock_level=Subquery(
                    active_policy.values("min_stock_level")[:1]
                ),
                reorder_qty=Subquery(active_policy.values("reorder_qty")[:1]),
            )
            .filter(
                Q(status__in=["EMPTY", "ALMOST_OUT"])
                | Q(
                    min_stock_level__isnull=False,
                    quantity_on_hand__lte=F("min_stock_level"),
                )
            )
            .select_related("product", "warehouse")
            .order_by("quantity_on_hand", "product__name")
            .values(
                "product_id",
                "product__sku",
                "product__name",
                "warehouse_id",
                "warehouse__name",
                "quantity_on_hand",
                "status",
                "min_stock_level",
                "reorder_qty",
            )[:limit]
        )

        return [
            {
                "product_id": row["product_id"],
                "sku": row["product__sku"],
                "product_name": row["product__name"],
                "warehouse_id": row["warehouse_id"],
                "warehouse_name": row["warehouse__name"],
                "quantity_on_hand": row["quantity_on_hand"],
                "status": row["status"],
                "min_stock_level": row["min_stock_level"],
                "reorder_qty": row["reorder_qty"],
            }
            for row in rows
        ]

    @staticmethod
    def _trunc_function(interval):
        if interval == "day":
            return TruncDay
        if interval == "week":
            return TruncWeek
        return TruncMonth

    @staticmethod
    def _movement_period_rows(queryset, period_expression):
        rows = (
            queryset.annotate(period=period_expression)
            .values("period")
            .annotate(
                count=Count("id"),
                total_quantity=Sum("total_quantity"),
            )
            .order_by("period")
        )
        return list(rows)
