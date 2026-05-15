"""
ReportsService — aggregated sales analytics queries.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Min, Q, Sum
from django.utils import timezone

from apps.sales.models import Invoice, Payment, SalesOrder, SalesOrderLine


class ReportsService:

    @staticmethod
    def daily_summary(report_date: date, warehouse_id=None) -> dict:
        orders = SalesOrder.objects.filter(
            order_date__date=report_date,
            status__in=["dispatched", "invoiced", "paid"],
        )
        if warehouse_id:
            orders = orders.filter(warehouse_id=warehouse_id)

        agg = orders.aggregate(
            total_transactions=Count("id"),
            total_revenue=Sum("total_amount"),
        )

        lines = SalesOrderLine.objects.filter(
            sales_order__in=orders,
            cogs_total__isnull=False,
        ).aggregate(total_cogs=Sum("cogs_total"))

        revenue = agg["total_revenue"] or Decimal("0")
        cogs = lines["total_cogs"] or Decimal("0")

        warehouse_name = None
        if warehouse_id:
            from central.models import Warehouse
            try:
                warehouse_name = Warehouse.objects.get(pk=warehouse_id).name
            except Warehouse.DoesNotExist:
                pass

        return {
            "date": report_date,
            "warehouse_id": warehouse_id,
            "warehouse_name": warehouse_name,
            "total_transactions": agg["total_transactions"] or 0,
            "total_revenue": revenue,
            "total_cogs": cogs,
            "gross_profit": revenue - cogs,
        }

    @staticmethod
    def revenue_by_product(date_from: date, date_to: date, warehouse_id=None) -> list:
        qs = SalesOrderLine.objects.filter(
            sales_order__order_date__date__gte=date_from,
            sales_order__order_date__date__lte=date_to,
            sales_order__status__in=["dispatched", "invoiced", "paid"],
        )
        if warehouse_id:
            qs = qs.filter(sales_order__warehouse_id=warehouse_id)

        rows = (
            qs.values("product__id", "product__name")
            .annotate(
                total_quantity_sold=Sum("quantity_dispatched"),
                total_revenue=Sum(
                    ExpressionWrapper(
                        F("quantity_dispatched") * F("unit_price"),
                        output_field=DecimalField(max_digits=14, decimal_places=2),
                    )
                ),
            )
            .order_by("-total_revenue")
        )
        return [
            {
                "product_id": r["product__id"],
                "product_name": r["product__name"],
                "total_quantity_sold": r["total_quantity_sold"] or Decimal("0"),
                "total_revenue": r["total_revenue"] or Decimal("0"),
            }
            for r in rows
        ]

    @staticmethod
    def margin_by_product(date_from: date, date_to: date, warehouse_id=None) -> list:
        qs = SalesOrderLine.objects.filter(
            sales_order__order_date__date__gte=date_from,
            sales_order__order_date__date__lte=date_to,
            sales_order__status__in=["dispatched", "invoiced", "paid"],
        )
        if warehouse_id:
            qs = qs.filter(sales_order__warehouse_id=warehouse_id)

        rows = (
            qs.values("product__id", "product__name")
            .annotate(
                total_revenue=Sum(
                    ExpressionWrapper(
                        F("quantity_dispatched") * F("unit_price"),
                        output_field=DecimalField(max_digits=14, decimal_places=2),
                    )
                ),
                total_cogs=Sum("cogs_total"),
            )
            .order_by("-total_revenue")
        )
        result = []
        for r in rows:
            revenue = r["total_revenue"] or Decimal("0")
            cogs = r["total_cogs"] or Decimal("0")
            profit = revenue - cogs
            margin_pct = (profit / revenue * 100) if revenue else None
            result.append({
                "product_id": r["product__id"],
                "product_name": r["product__name"],
                "total_revenue": revenue,
                "total_cogs": cogs,
                "gross_profit": profit,
                "margin_percentage": margin_pct,
            })
        return result

    @staticmethod
    def customer_statement(customer_id) -> dict:
        from apps.sales.models import Customer, Payment
        from apps.sales.serializers.sales_order_serializer import SalesOrderListSerializer
        from apps.sales.serializers.invoice_serializers import InvoiceListSerializer
        from apps.sales.serializers.payment_serializers import PaymentSerializer

        from django.shortcuts import get_object_or_404
        customer = Customer.objects.get(pk=customer_id)

        orders = SalesOrder.objects.filter(customer=customer).order_by("-order_date")
        invoices = Invoice.objects.filter(sales_order__customer=customer).order_by("-issued_date")
        payments = Payment.objects.filter(customer=customer).order_by("-payment_date")

        total_ordered = orders.aggregate(t=Sum("total_amount"))["t"] or Decimal("0")
        total_invoiced = invoices.aggregate(t=Sum("total_amount"))["t"] or Decimal("0")
        total_paid = payments.aggregate(t=Sum("amount"))["t"] or Decimal("0")
        outstanding = total_invoiced - total_paid

        return {
            "customer_id": customer.id,
            "customer_name": customer.name,
            "total_ordered": total_ordered,
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "outstanding_balance": outstanding,
            "orders": SalesOrderListSerializer(orders, many=True).data,
            "invoices": InvoiceListSerializer(invoices, many=True).data,
            "payments": PaymentSerializer(payments, many=True).data,
        }

    @staticmethod
    def outstanding_debtors() -> list:
        from django.utils import timezone
        today = timezone.now().date()

        invoices = (
            Invoice.objects.filter(status__in=["issued", "partially_paid", "overdue"])
            .select_related("sales_order__customer")
            .values(
                "sales_order__customer__id",
                "sales_order__customer__name",
                "sales_order__customer__company_name",
            )
            .annotate(
                outstanding_balance=Sum("total_amount"),
                oldest_due_date=Min("due_date"),
            )
            .order_by("-outstanding_balance")
        )

        result = []
        for row in invoices:
            oldest = row["oldest_due_date"]
            days_overdue = (today - oldest).days if oldest and oldest < today else None
            result.append({
                "customer_id": row["sales_order__customer__id"],
                "customer_name": row["sales_order__customer__name"],
                "company_name": row["sales_order__customer__company_name"],
                "outstanding_balance": row["outstanding_balance"] or Decimal("0"),
                "oldest_due_date": oldest,
                "days_overdue": days_overdue,
            })
        return result

    @staticmethod
    def sales_by_warehouse(date_from: date, date_to: date) -> list:
        rows = (
            SalesOrder.objects.filter(
                order_date__date__gte=date_from,
                order_date__date__lte=date_to,
                status__in=["dispatched", "invoiced", "paid"],
            )
            .values("warehouse__id", "warehouse__name")
            .annotate(
                total_orders=Count("id"),
                total_revenue=Sum("total_amount"),
            )
            .order_by("-total_revenue")
        )

        result = []
        for r in rows:
            revenue = r["total_revenue"] or Decimal("0")
            cogs = (
                SalesOrderLine.objects.filter(
                    sales_order__warehouse_id=r["warehouse__id"],
                    sales_order__order_date__date__gte=date_from,
                    sales_order__order_date__date__lte=date_to,
                    sales_order__status__in=["dispatched", "invoiced", "paid"],
                    cogs_total__isnull=False,
                ).aggregate(t=Sum("cogs_total"))["t"] or Decimal("0")
            )
            result.append({
                "warehouse_id": r["warehouse__id"],
                "warehouse_name": r["warehouse__name"],
                "total_orders": r["total_orders"],
                "total_revenue": revenue,
                "total_cogs": cogs,
                "gross_profit": revenue - cogs,
            })
        return result
