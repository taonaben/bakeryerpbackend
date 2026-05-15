from decimal import Decimal

from django.db.models import Count, Max, Min, Q, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from django.utils import timezone

from apps.production.models import (
    BatchOutput,
    BatchWaste,
    ProductionBatch,
    ProductionOrder,
    ReworkOrder,
)


PRODUCTION_STATUSES = ["scheduled", "in_progress", "completed", "cancelled"]
REWORK_STATUSES = ["scheduled", "in_progress", "completed", "cancelled"]


class ProductionOverviewService:
    @staticmethod
    def summary(company, *, date_from=None, date_to=None, warehouse_id=None, limit=10):
        today = timezone.localdate()

        orders = ProductionOrder.objects.filter(warehouse__company=company)
        rework_orders = ReworkOrder.objects.filter(warehouse__company=company)
        batches = ProductionBatch.objects.filter(
            production_order__warehouse__company=company
        )

        if warehouse_id:
            orders = orders.filter(warehouse_id=warehouse_id)
            rework_orders = rework_orders.filter(warehouse_id=warehouse_id)
            batches = batches.filter(production_order__warehouse_id=warehouse_id)

        completed_orders = orders.filter(status="completed")
        if date_from:
            completed_orders = completed_orders.filter(scheduled_end__date__gte=date_from)
        if date_to:
            completed_orders = completed_orders.filter(scheduled_end__date__lte=date_to)

        finished_totals = ProductionOverviewService._finished_order_totals(
            completed_orders
        )

        scheduled_overdue = orders.filter(
            status="scheduled",
            scheduled_start__date__lt=today,
        )

        return {
            "as_of_date": today,
            "date_from": date_from,
            "date_to": date_to,
            "warehouse_id": warehouse_id,
            "production_order_counts_by_status": ProductionOverviewService._count_by_status(
                orders, PRODUCTION_STATUSES
            ),
            "rework_order_counts_by_status": ProductionOverviewService._count_by_status(
                rework_orders, REWORK_STATUSES
            ),
            "wip_order_count": orders.filter(status="in_progress").count(),
            "in_progress_batch_count": batches.filter(status="in_progress").count(),
            "scheduled_orders_overdue_to_start": scheduled_overdue.count(),
            "completed_quantity": finished_totals["actual_output"],
            "expected_vs_actual_output": {
                "expected_output": finished_totals["expected_output"],
                "actual_output": finished_totals["actual_output"],
            },
            "waste": {
                "quantity": finished_totals["actual_waste"],
                "waste_rate": ProductionOverviewService._safe_percent(
                    finished_totals["actual_waste"],
                    finished_totals["actual_output"] + finished_totals["actual_waste"],
                ),
            },
            "variance": {
                "quantity": finished_totals["variance"],
                "variance_rate": ProductionOverviewService._safe_percent(
                    finished_totals["variance"],
                    finished_totals["expected_output"],
                ),
            },
            "top_products_produced": ProductionOverviewService._top_products_produced(
                company,
                date_from=date_from,
                date_to=date_to,
                warehouse_id=warehouse_id,
                limit=limit,
            ),
        }

    @staticmethod
    def wip(company, *, warehouse_id=None, limit=20):
        now = timezone.now()
        today = timezone.localdate()

        orders = ProductionOrder.objects.filter(warehouse__company=company)
        batches = ProductionBatch.objects.filter(
            production_order__warehouse__company=company
        )

        if warehouse_id:
            orders = orders.filter(warehouse_id=warehouse_id)
            batches = batches.filter(production_order__warehouse_id=warehouse_id)

        blocked_orders = orders.filter(status="scheduled").filter(
            Q(formula__status__in=["draft", "on_hold", "deactivated", "archived"])
            | Q(formula__is_active=False)
            | Q(formula__on_hold=True)
        )

        return {
            "as_of_date": today,
            "warehouse_id": warehouse_id,
            "in_progress_orders": ProductionOverviewService._order_rows(
                orders.filter(status="in_progress").order_by("scheduled_start")[:limit]
            ),
            "in_progress_batches": ProductionOverviewService._batch_rows(
                batches.filter(status="in_progress").order_by("started_at")[:limit]
            ),
            "scheduled_orders_due_today": ProductionOverviewService._order_rows(
                orders.filter(
                    status="scheduled",
                    scheduled_start__date=today,
                ).order_by("scheduled_start")[:limit]
            ),
            "scheduled_orders_overdue": ProductionOverviewService._order_rows(
                orders.filter(
                    status="scheduled",
                    scheduled_start__lt=now,
                ).order_by("scheduled_start")[:limit]
            ),
            "orders_blocked_by_unavailable_formula": ProductionOverviewService._blocked_order_rows(
                blocked_orders.order_by("scheduled_start")[:limit]
            ),
        }

    @staticmethod
    def yield_trends(
        company,
        *,
        date_from=None,
        date_to=None,
        warehouse_id=None,
        interval="month",
    ):
        orders = ProductionOrder.objects.filter(
            warehouse__company=company,
            status="completed",
        )
        if warehouse_id:
            orders = orders.filter(warehouse_id=warehouse_id)
        if date_from:
            orders = orders.filter(scheduled_end__date__gte=date_from)
        if date_to:
            orders = orders.filter(scheduled_end__date__lte=date_to)

        trunc = ProductionOverviewService._trunc_function(interval)

        output_rows = ProductionOverviewService._finished_order_trend_rows(
            orders,
            trunc("scheduled_end"),
        )
        waste_rows = ProductionOverviewService._waste_trend_rows(
            company,
            date_from=date_from,
            date_to=date_to,
            warehouse_id=warehouse_id,
            trunc=trunc,
        )

        return {
            "date_from": date_from,
            "date_to": date_to,
            "warehouse_id": warehouse_id,
            "interval": interval,
            "output": output_rows,
            "waste": waste_rows,
            "variance_by_product": ProductionOverviewService._variance_by_product(
                orders
            ),
        }

    @staticmethod
    def schedule_adherence(
        company,
        *,
        date_from=None,
        date_to=None,
        warehouse_id=None,
        limit=20,
    ):
        orders = ProductionOrder.objects.filter(
            warehouse__company=company,
            status="completed",
        )
        if warehouse_id:
            orders = orders.filter(warehouse_id=warehouse_id)
        if date_from:
            orders = orders.filter(scheduled_end__date__gte=date_from)
        if date_to:
            orders = orders.filter(scheduled_end__date__lte=date_to)

        rows = []
        order_rows = (
            orders.select_related("product", "warehouse")
            .annotate(
                first_batch_started_at=Min("batches__started_at"),
                last_batch_completed_at=Max("batches__completed_at"),
            )
            .order_by("-scheduled_end")[:limit]
        )

        on_time_start_count = 0
        on_time_finish_count = 0
        completed_with_batch_count = 0

        for order in order_rows:
            started_at = order.first_batch_started_at
            completed_at = order.last_batch_completed_at
            start_delay_minutes = None
            finish_delay_minutes = None

            if started_at:
                start_delay_minutes = ProductionOverviewService._minutes_between(
                    order.scheduled_start, started_at
                )
                if started_at <= order.scheduled_start:
                    on_time_start_count += 1

            if completed_at:
                completed_with_batch_count += 1
                finish_delay_minutes = ProductionOverviewService._minutes_between(
                    order.scheduled_end, completed_at
                )
                if completed_at <= order.scheduled_end:
                    on_time_finish_count += 1

            rows.append(
                {
                    "order_id": order.id,
                    "product_id": order.product_id,
                    "product_name": order.product.name,
                    "warehouse_id": order.warehouse_id,
                    "warehouse_name": order.warehouse.name,
                    "scheduled_start": order.scheduled_start,
                    "scheduled_end": order.scheduled_end,
                    "first_batch_started_at": started_at,
                    "last_batch_completed_at": completed_at,
                    "start_delay_minutes": start_delay_minutes,
                    "finish_delay_minutes": finish_delay_minutes,
                }
            )

        return {
            "date_from": date_from,
            "date_to": date_to,
            "warehouse_id": warehouse_id,
            "on_time_start_rate": ProductionOverviewService._safe_percent(
                Decimal(str(on_time_start_count)), Decimal(str(len(rows)))
            ),
            "on_time_finish_rate": ProductionOverviewService._safe_percent(
                Decimal(str(on_time_finish_count)),
                Decimal(str(completed_with_batch_count)),
            ),
            "orders": rows,
        }

    @staticmethod
    def _count_by_status(queryset, statuses):
        counts = {
            row["status"]: row["count"]
            for row in queryset.values("status").annotate(count=Count("id"))
        }
        return {status: counts.get(status, 0) for status in statuses}

    @staticmethod
    def _finished_order_totals(orders):
        totals = {
            "expected_output": Decimal("0"),
            "actual_output": Decimal("0"),
            "actual_waste": Decimal("0"),
            "variance": Decimal("0"),
        }
        for row in ProductionOverviewService._finished_order_rows(orders):
            totals["expected_output"] += row["expected_output"]
            totals["actual_output"] += row["actual_output"]
            totals["actual_waste"] += row["actual_waste"]
            totals["variance"] += row["variance"]
        return totals

    @staticmethod
    def _finished_order_rows(orders):
        result = []
        qs = orders.select_related("product", "warehouse", "formula").prefetch_related(
            "batches__outputs",
            "batches__waste",
        )
        for order in qs:
            expected_output = Decimal(str(order.quantity or 0))
            actual_output = Decimal("0")
            actual_waste = Decimal("0")

            for batch in order.batches.all():
                for output in batch.outputs.all():
                    if output.product_id == order.product_id:
                        actual_output += Decimal(str(output.quantity_produced or 0))
                for waste in batch.waste.all():
                    actual_waste += Decimal(str(waste.quantity_wasted or 0))

            result.append(
                {
                    "order": order,
                    "expected_output": expected_output,
                    "actual_output": actual_output,
                    "actual_waste": actual_waste,
                    "variance": expected_output - actual_output,
                }
            )
        return result

    @staticmethod
    def _top_products_produced(company, *, date_from, date_to, warehouse_id, limit):
        outputs = BatchOutput.objects.filter(
            production_batch__production_order__warehouse__company=company,
            production_batch__production_order__status="completed",
        )
        if warehouse_id:
            outputs = outputs.filter(
                production_batch__production_order__warehouse_id=warehouse_id
            )
        if date_from:
            outputs = outputs.filter(
                production_batch__production_order__scheduled_end__date__gte=date_from
            )
        if date_to:
            outputs = outputs.filter(
                production_batch__production_order__scheduled_end__date__lte=date_to
            )

        rows = (
            outputs.values("product_id", "product__name")
            .annotate(total_quantity=Sum("quantity_produced"), batch_count=Count("id"))
            .order_by("-total_quantity")[:limit]
        )
        return [
            {
                "product_id": row["product_id"],
                "product_name": row["product__name"],
                "total_quantity": Decimal(str(row["total_quantity"] or 0)),
                "batch_count": row["batch_count"],
            }
            for row in rows
        ]

    @staticmethod
    def _order_rows(orders):
        return [
            ProductionOverviewService._order_row(order)
            for order in orders.select_related("product", "warehouse", "formula")
        ]

    @staticmethod
    def _batch_rows(batches):
        return [
            {
                "batch_id": batch.id,
                "batch_number": batch.batch_number,
                "order_id": batch.production_order_id,
                "product_id": batch.production_order.product_id,
                "product_name": batch.production_order.product.name,
                "warehouse_id": batch.production_order.warehouse_id,
                "warehouse_name": batch.production_order.warehouse.name,
                "quantity_produced": Decimal(str(batch.quantity_produced or 0)),
                "status": batch.status,
                "started_at": batch.started_at,
                "completed_at": batch.completed_at,
            }
            for batch in batches.select_related(
                "production_order__product",
                "production_order__warehouse",
            )
        ]

    @staticmethod
    def _blocked_order_rows(orders):
        rows = []
        for order in orders.select_related("product", "warehouse", "formula"):
            reasons = []
            if order.formula.status != "active":
                reasons.append(f"Formula status is {order.formula.status}")
            if not order.formula.is_active:
                reasons.append("Formula is inactive")
            if order.formula.on_hold:
                reasons.append("Formula is on hold")
            rows.append(
                ProductionOverviewService._order_row(order, blocking_reasons=reasons)
            )
        return rows

    @staticmethod
    def _order_row(order, *, blocking_reasons=None):
        row = {
            "order_id": order.id,
            "product_id": order.product_id,
            "product_name": order.product.name,
            "warehouse_id": order.warehouse_id,
            "warehouse_name": order.warehouse.name,
            "quantity": Decimal(str(order.quantity or 0)),
            "status": order.status,
            "scheduled_start": order.scheduled_start,
            "scheduled_end": order.scheduled_end,
            "formula_id": order.formula_id,
            "formula_name": order.formula.name if order.formula else None,
        }
        if blocking_reasons is not None:
            row["blocking_reasons"] = blocking_reasons
        return row

    @staticmethod
    def _finished_order_trend_rows(orders, period_expression):
        rows_by_period = {}
        period_rows = orders.annotate(period=period_expression).values("id", "period")
        periods = {row["id"]: row["period"] for row in period_rows}

        for row in ProductionOverviewService._finished_order_rows(orders):
            order = row["order"]
            period = periods.get(order.id)
            if period is None:
                continue
            bucket = rows_by_period.setdefault(
                period,
                {
                    "period": period,
                    "expected_output": Decimal("0"),
                    "actual_output": Decimal("0"),
                    "variance": Decimal("0"),
                    "completed_orders": 0,
                },
            )
            bucket["expected_output"] += row["expected_output"]
            bucket["actual_output"] += row["actual_output"]
            bucket["variance"] += row["variance"]
            bucket["completed_orders"] += 1

        return [rows_by_period[key] for key in sorted(rows_by_period)]

    @staticmethod
    def _waste_trend_rows(company, *, date_from, date_to, warehouse_id, trunc):
        waste = BatchWaste.objects.filter(
            production_batch__production_order__warehouse__company=company,
            production_batch__completed_at__isnull=False,
        )
        if warehouse_id:
            waste = waste.filter(production_batch__production_order__warehouse_id=warehouse_id)
        if date_from:
            waste = waste.filter(production_batch__completed_at__date__gte=date_from)
        if date_to:
            waste = waste.filter(production_batch__completed_at__date__lte=date_to)

        rows = (
            waste.annotate(period=trunc("production_batch__completed_at"))
            .values("period")
            .annotate(quantity=Sum("quantity_wasted"), line_count=Count("id"))
            .order_by("period")
        )
        return [
            {
                "period": row["period"],
                "quantity": Decimal(str(row["quantity"] or 0)),
                "line_count": row["line_count"],
            }
            for row in rows
        ]

    @staticmethod
    def _variance_by_product(orders):
        rows_by_product = {}
        for row in ProductionOverviewService._finished_order_rows(orders):
            order = row["order"]
            bucket = rows_by_product.setdefault(
                order.product_id,
                {
                    "product_id": order.product_id,
                    "product_name": order.product.name,
                    "expected_output": Decimal("0"),
                    "actual_output": Decimal("0"),
                    "variance": Decimal("0"),
                    "completed_orders": 0,
                },
            )
            bucket["expected_output"] += row["expected_output"]
            bucket["actual_output"] += row["actual_output"]
            bucket["variance"] += row["variance"]
            bucket["completed_orders"] += 1

        return sorted(
            rows_by_product.values(),
            key=lambda item: abs(item["variance"]),
            reverse=True,
        )

    @staticmethod
    def _trunc_function(interval):
        if interval == "day":
            return TruncDay
        if interval == "week":
            return TruncWeek
        return TruncMonth

    @staticmethod
    def _safe_percent(numerator, denominator):
        if not denominator:
            return None
        return numerator / denominator * Decimal("100")

    @staticmethod
    def _minutes_between(expected, actual):
        return (actual - expected).total_seconds() / 60
