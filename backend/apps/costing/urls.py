from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.costing.views.overhead_rate_views import OverheadRateViewSet
from apps.costing.views.standard_cost_views import StandardCostViewSet
from apps.costing.views.costing_views import CostingEntryViewSet
from apps.costing.views.variance_views import CostVarianceViewSet
from apps.costing.views.product_pricing_rule_views import ProductPricingRuleViewSet
from apps.costing.views.product_costing_views import (
    BatchCostingEntryView,
    ProductLatestStandardCostView,
    ProductPricingRuleDetailView,
)
from apps.costing.views.reports_views import (
    CostTrendView,
    IngredientCostBreakdownView,
    MarginReportView,
    VarianceAnalysisView,
)
from apps.costing.views.cogs_posting_views import COGSPostView

router = DefaultRouter(trailing_slash=False)
router.register(r"overhead-rates", OverheadRateViewSet, basename="overhead-rate")
router.register(r"standard-costs", StandardCostViewSet, basename="standard-cost")
router.register(r"costing-entries", CostingEntryViewSet, basename="costing-entry")
router.register(r"variances", CostVarianceViewSet, basename="variance")
router.register(r"pricing-rules", ProductPricingRuleViewSet, basename="pricing-rule")

urlpatterns = [
    # ViewSet routes
    path("", include(router.urls)),

    # Cross-module product-scoped endpoints
    path(
        "products/<uuid:product_id>/standard-cost/latest",
        ProductLatestStandardCostView.as_view(),
        name="product-latest-standard-cost",
    ),
    path(
        "products/<uuid:product_id>/pricing-rule",
        ProductPricingRuleDetailView.as_view(),
        name="product-pricing-rule",
    ),

    # Production batch costing entry lookup
    path(
        "production/batches/<uuid:batch_id>/costing-entry",
        BatchCostingEntryView.as_view(),
        name="batch-costing-entry",
    ),

    # COGS manual trigger
    path("cogs/post", COGSPostView.as_view(), name="cogs-post"),

    # Analytics & reporting
    path(
        "reports/cost-trend/<uuid:product_id>",
        CostTrendView.as_view(),
        name="report-cost-trend",
    ),
    path(
        "reports/variance-analysis",
        VarianceAnalysisView.as_view(),
        name="report-variance-analysis",
    ),
    path(
        "reports/margin-report",
        MarginReportView.as_view(),
        name="report-margin",
    ),
    path(
        "reports/ingredient-cost-breakdown",
        IngredientCostBreakdownView.as_view(),
        name="report-ingredient-cost",
    ),
]
