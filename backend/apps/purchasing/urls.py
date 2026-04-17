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
from .views.supplier_views import (
    SupplierContactViewSet,
    SupplierDocumentViewSet,
    SupplierViewSet,
)


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

# Nested routes: /suppliers/{supplier_pk}/contacts/ and /suppliers/{supplier_pk}/documents/
contact_list = SupplierContactViewSet.as_view({"get": "list", "post": "create"})
contact_detail = SupplierContactViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
document_list = SupplierDocumentViewSet.as_view({"get": "list", "post": "create"})
document_detail = SupplierDocumentViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "suppliers/<uuid:supplier_pk>/contacts/",
        contact_list,
        name="supplier-contact-list",
    ),
    path(
        "suppliers/<uuid:supplier_pk>/contacts/<uuid:pk>/",
        contact_detail,
        name="supplier-contact-detail",
    ),
    path(
        "suppliers/<uuid:supplier_pk>/documents/",
        document_list,
        name="supplier-document-list",
    ),
    path(
        "suppliers/<uuid:supplier_pk>/documents/<uuid:pk>/",
        document_detail,
        name="supplier-document-detail",
    ),
]
