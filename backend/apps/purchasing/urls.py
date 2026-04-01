from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views.goods_receipt_views import GoodsReceiptViewSet
from .views.purchasing_order_views import (
    PurchaseOrderLineItemViewSet,
    PurchaseOrderViewSet,
)


router = DefaultRouter()
router.register("purchase-orders", PurchaseOrderViewSet, basename="purchase-orders")
# router.register(
#     "purchase-order-lines",
#     PurchaseOrderLineItemViewSet,
#     basename="purchase-order-lines",
# )
router.register("goods-receipts", GoodsReceiptViewSet, basename="goods-receipts")

urlpatterns = [
    path("", include(router.urls)),
]
