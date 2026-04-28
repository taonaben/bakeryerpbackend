from django.urls import path

from apps.finance.views.fiscal_period_views import (
    FiscalPeriodCloseView,
    FiscalPeriodDetailView,
    FiscalPeriodListView,
)
from apps.finance.views.coa_views import (
    ChartOfAccountsDetailView,
    ChartOfAccountsListView,
    SeedAccountsView,
)
from apps.finance.views.journal_views import (
    JournalEntryDetailView,
    JournalEntryListView,
    JournalEntryReverseView,
)
from apps.finance.views.ar_views import ARByCustomerView, ARDetailView, ARListView
from apps.finance.views.ap_views import APBySupplierView, APDetailView, APListView, APPayView
from apps.finance.views.reports_views import (
    APAgingView,
    ARAgingView,
    BalanceSheetView,
    IncomeStatementView,
    TrialBalanceView,
)

urlpatterns = [
    # ── Fiscal Periods
    path("fiscal-periods", FiscalPeriodListView.as_view(), name="fiscal-period-list"),
    path("fiscal-periods/<uuid:pk>", FiscalPeriodDetailView.as_view(), name="fiscal-period-detail"),
    path("fiscal-periods/<uuid:pk>/close", FiscalPeriodCloseView.as_view(), name="fiscal-period-close"),

    # ── Chart of Accounts
    path("accounts", ChartOfAccountsListView.as_view(), name="coa-list"),
    path("accounts/seed", SeedAccountsView.as_view(), name="coa-seed"),
    path("accounts/<uuid:pk>", ChartOfAccountsDetailView.as_view(), name="coa-detail"),

    # ── Journal Entries
    path("journal-entries", JournalEntryListView.as_view(), name="journal-entry-list"),
    path("journal-entries/<uuid:pk>", JournalEntryDetailView.as_view(), name="journal-entry-detail"),
    path("journal-entries/<uuid:pk>/reverse", JournalEntryReverseView.as_view(), name="journal-entry-reverse"),

    # ── Accounts Receivable
    path("ar", ARListView.as_view(), name="ar-list"),
    path("ar/<uuid:pk>", ARDetailView.as_view(), name="ar-detail"),
    path("ar/customer/<uuid:customer_id>", ARByCustomerView.as_view(), name="ar-by-customer"),

    # ── Accounts Payable
    path("ap", APListView.as_view(), name="ap-list"),
    path("ap/<uuid:pk>", APDetailView.as_view(), name="ap-detail"),
    path("ap/supplier/<uuid:supplier_id>", APBySupplierView.as_view(), name="ap-by-supplier"),
    path("ap/<uuid:pk>/pay", APPayView.as_view(), name="ap-pay"),

    # ── Reports
    path("reports/trial-balance", TrialBalanceView.as_view(), name="report-trial-balance"),
    path("reports/income-statement", IncomeStatementView.as_view(), name="report-income-statement"),
    path("reports/balance-sheet", BalanceSheetView.as_view(), name="report-balance-sheet"),
    path("reports/ar-aging", ARAgingView.as_view(), name="report-ar-aging"),
    path("reports/ap-aging", APAgingView.as_view(), name="report-ap-aging"),
]
