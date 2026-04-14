from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views.goods_receipt_views import GoodsReceiptViewSet
from .views.invoice_views import SupplierInvoiceViewSet
from .views.purchasing_order_views import (
    PurchaseOrderLineItemViewSet,
    PurchaseOrderViewSet,
)
from .views.requisition_views import (
    PurchaseRequisitionLineItemViewSet,
    PurchaseRequisitionViewSet,
)
from .views.supplier_views import SupplierViewSet


router = DefaultRouter()
router.register("suppliers", SupplierViewSet, basename="suppliers")
router.register("purchase-orders", PurchaseOrderViewSet, basename="purchase-orders")
# router.register(
#     "purchase-order-lines",
#     PurchaseOrderLineItemViewSet,
#     basename="purchase-order-lines",
# )
router.register("goods-receipts", GoodsReceiptViewSet, basename="goods-receipts")
router.register(
    "supplier-invoices", SupplierInvoiceViewSet, basename="supplier-invoices"
)
router.register(
    "purchase-requisitions",
    PurchaseRequisitionViewSet,
    basename="purchase-requisitions",
)
# router.register(
#     "purchase-requisition-lines",
#     PurchaseRequisitionLineItemViewSet,
#     basename="purchase-requisition-lines",
# )

urlpatterns = [
    path("", include(router.urls)),
]
