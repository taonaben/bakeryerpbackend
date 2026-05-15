from django.urls import path

from apps.sales.views.customer_views import CustomerViewSet
from apps.sales.views.dispatch_views import DeliveryViewSet, DispatchOrderView
from apps.sales.views.invoice_views import InvoicePDFView, InvoiceViewSet, OrderInvoiceView
from apps.sales.views.payment_views import InvoicePaymentView, PaymentViewSet
from apps.sales.views.pricing_views import ResolvePriceView
from apps.sales.views.reports_views import (
    CustomerStatementView,
    DailySummaryView,
    MarginByProductView,
    OutstandingDebtorsView,
    RevenueByProductView,
    SalesByWarehouseView,
)
from apps.sales.views.sales_order_views import SalesOrderViewSet

# ── Customers ──────────────────────────────────────────────────────────────
customer_list = CustomerViewSet.as_view({"get": "list", "post": "create"})
customer_detail = CustomerViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"})
customer_orders = CustomerViewSet.as_view({"get": "orders"})
customer_invoices = CustomerViewSet.as_view({"get": "invoices"})
customer_payments = CustomerViewSet.as_view({"get": "payments"})
customer_outstanding = CustomerViewSet.as_view({"get": "outstanding"})
customer_pricing = CustomerViewSet.as_view({"get": "pricing", "post": "pricing"})
customer_pricing_detail = CustomerViewSet.as_view({"patch": "pricing_detail", "delete": "pricing_detail"})

# ── Sales Orders ────────────────────────────────────────────────────────────
order_list = SalesOrderViewSet.as_view({"get": "list", "post": "create"})
order_detail = SalesOrderViewSet.as_view({"get": "retrieve", "patch": "partial_update"})
order_lines = SalesOrderViewSet.as_view({"post": "add_line"})
order_line_detail = SalesOrderViewSet.as_view({"patch": "line_detail", "delete": "line_detail"})
order_confirm = SalesOrderViewSet.as_view({"post": "confirm"})
order_cancel = SalesOrderViewSet.as_view({"post": "cancel"})
order_deliveries = SalesOrderViewSet.as_view({"get": "deliveries"})
pos_sale = SalesOrderViewSet.as_view({"post": "pos_sale"})

# ── Deliveries ──────────────────────────────────────────────────────────────
delivery_list = DeliveryViewSet.as_view({"get": "list"})
delivery_detail = DeliveryViewSet.as_view({"get": "retrieve"})
delivery_confirm_receipt = DeliveryViewSet.as_view({"patch": "confirm_receipt"})
delivery_fail = DeliveryViewSet.as_view({"patch": "fail_delivery"})

# ── Invoices ────────────────────────────────────────────────────────────────
invoice_list = InvoiceViewSet.as_view({"get": "list"})
invoice_detail = InvoiceViewSet.as_view({"get": "retrieve"})
invoice_cancel = InvoiceViewSet.as_view({"post": "cancel"})

# ── Payments ────────────────────────────────────────────────────────────────
payment_list = PaymentViewSet.as_view({"get": "list"})

urlpatterns = [
    # ── Customers
    path("customers", customer_list, name="customer-list"),
    path("customers/<uuid:pk>", customer_detail, name="customer-detail"),
    path("customers/<uuid:pk>/orders", customer_orders, name="customer-orders"),
    path("customers/<uuid:pk>/invoices", customer_invoices, name="customer-invoices"),
    path("customers/<uuid:pk>/payments", customer_payments, name="customer-payments"),
    path("customers/<uuid:pk>/outstanding", customer_outstanding, name="customer-outstanding"),
    path("customers/<uuid:pk>/pricing", customer_pricing, name="customer-pricing"),
    path("customers/<uuid:pk>/pricing/<uuid:agreement_id>", customer_pricing_detail, name="customer-pricing-detail"),

    # ── Pricing resolution
    path("pricing/resolve", ResolvePriceView.as_view(), name="pricing-resolve"),

    # ── Sales Orders
    path("orders", order_list, name="order-list"),
    path("orders/pos", pos_sale, name="order-pos"),
    path("orders/<uuid:pk>", order_detail, name="order-detail"),
    path("orders/<uuid:pk>/lines", order_lines, name="order-lines"),
    path("orders/<uuid:pk>/lines/<uuid:line_id>", order_line_detail, name="order-line-detail"),
    path("orders/<uuid:pk>/confirm", order_confirm, name="order-confirm"),
    path("orders/<uuid:pk>/cancel", order_cancel, name="order-cancel"),
    path("orders/<uuid:pk>/deliveries", order_deliveries, name="order-deliveries"),
    path("orders/<uuid:order_id>/dispatch", DispatchOrderView.as_view(), name="order-dispatch"),
    path("orders/<uuid:order_id>/invoice", OrderInvoiceView.as_view(), name="order-invoice"),
    path("orders/<uuid:order_id>/invoice/generate", OrderInvoiceView.as_view(), name="order-invoice-generate"),

    # ── Deliveries
    path("deliveries", delivery_list, name="delivery-list"),
    path("deliveries/<uuid:pk>", delivery_detail, name="delivery-detail"),
    path("deliveries/<uuid:pk>/confirm-receipt", delivery_confirm_receipt, name="delivery-confirm-receipt"),
    path("deliveries/<uuid:pk>/fail", delivery_fail, name="delivery-fail"),

    # ── Invoices
    path("invoices", invoice_list, name="invoice-list"),
    path("invoices/<uuid:pk>", invoice_detail, name="invoice-detail"),
    path("invoices/<uuid:pk>/cancel", invoice_cancel, name="invoice-cancel"),
    path("invoices/<uuid:pk>/pdf", InvoicePDFView.as_view(), name="invoice-pdf"),
    path("invoices/<uuid:invoice_id>/payments", InvoicePaymentView.as_view(), name="invoice-payments"),

    # ── Payments
    path("payments", payment_list, name="payment-list"),

    # ── Reports
    path("reports/daily-summary", DailySummaryView.as_view(), name="report-daily-summary"),
    path("reports/revenue-by-product", RevenueByProductView.as_view(), name="report-revenue-by-product"),
    path("reports/margin-by-product", MarginByProductView.as_view(), name="report-margin-by-product"),
    path("reports/customer-statement/<uuid:customer_id>", CustomerStatementView.as_view(), name="report-customer-statement"),
    path("reports/outstanding-debtors", OutstandingDebtorsView.as_view(), name="report-outstanding-debtors"),
    path("reports/sales-by-warehouse", SalesByWarehouseView.as_view(), name="report-sales-by-warehouse"),
]
