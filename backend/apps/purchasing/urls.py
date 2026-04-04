from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views.goods_receipt_views import GoodsReceiptViewSet
from .views.purchasing_order_views import (
    PurchaseOrderLineItemViewSet,
    PurchaseOrderViewSet,
)
from .views.requisition_views import (
    PurchaseRequisitionLineItemViewSet,
    PurchaseRequisitionViewSet,
)


router = DefaultRouter()
router.register("purchase-orders", PurchaseOrderViewSet, basename="purchase-orders")
# router.register(
#     "purchase-order-lines",
#     PurchaseOrderLineItemViewSet,
#     basename="purchase-order-lines",
# )
router.register("goods-receipts", GoodsReceiptViewSet, basename="goods-receipts")
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
