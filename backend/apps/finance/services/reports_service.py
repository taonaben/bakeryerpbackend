"""
FinanceReportsService — derives Trial Balance, Income Statement,
Balance Sheet, and Aging reports from JournalEntryLine records.
No additional models needed — everything is read from the ledger.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounting.models import Account, FiscalPeriod, JournalEntry, JournalEntryLine
from apps.finance.models import AccountsPayable, AccountsReceivable
from central.models import Company


class FinanceReportsService:

    # ------------------------------------------------------------------ #
    # Trial Balance                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def trial_balance(company: Company, date_from: date, date_to: date,
                      fiscal_period_id=None) -> dict:
        lines_qs = JournalEntryLine.objects.filter(
            journal_entry__company=company,
            journal_entry__entry_date__gte=date_from,
            journal_entry__entry_date__lte=date_to,
            journal_entry__is_balanced=True,
        )
        if fiscal_period_id:
            lines_qs = lines_qs.filter(journal_entry__fiscal_period_id=fiscal_period_id)

        rows = (
            lines_qs
            .values("account__code", "account__name", "account__account_type",
                    "account__updated_at")
            .annotate(
                total_debits=Sum("debit"),
                total_credits=Sum("credit"),
            )
            .order_by("account__code")
        )

        result_lines = []
        grand_debits = Decimal("0")
        grand_credits = Decimal("0")

        for row in rows:
            dr = row["total_debits"] or Decimal("0")
            cr = row["total_credits"] or Decimal("0")
            balance = dr - cr
            grand_debits += dr
            grand_credits += cr

            # Determine normal_balance from account type
            acct_type = row["account__account_type"].lower()
            normal = "debit" if acct_type in ("asset", "expense") else "credit"

            result_lines.append({
                "account_code": row["account__code"],
                "account_name": row["account__name"],
                "account_type": acct_type,
                "account_subtype": "",
                "total_debits": dr,
                "total_credits": cr,
                "balance": balance,
                "normal_balance": normal,
            })

        period_name = None
        if fiscal_period_id:
            try:
                period_name = FiscalPeriod.objects.get(pk=fiscal_period_id).name
            except FiscalPeriod.DoesNotExist:
                pass

        return {
            "date_from": date_from,
            "date_to": date_to,
            "fiscal_period": period_name,
            "total_debits": grand_debits,
            "total_credits": grand_credits,
            "is_balanced": grand_debits == grand_credits,
            "lines": result_lines,
        }

    # ------------------------------------------------------------------ #
    # Income Statement                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def income_statement(company: Company, date_from: date, date_to: date) -> dict:
        def _get_lines(account_types):
            return (
                JournalEntryLine.objects.filter(
                    journal_entry__company=company,
                    journal_entry__entry_date__gte=date_from,
                    journal_entry__entry_date__lte=date_to,
                    journal_entry__is_balanced=True,
                    account__account_type__in=account_types,
                )
                .values("account__code", "account__name")
                .annotate(
                    total_debits=Sum("debit"),
                    total_credits=Sum("credit"),
                )
                .order_by("account__code")
            )

        def _net(row, normal_balance):
            dr = row["total_debits"] or Decimal("0")
            cr = row["total_credits"] or Decimal("0")
            return cr - dr if normal_balance == "credit" else dr - cr

        revenue_rows = _get_lines(["Revenue"])
        expense_rows = _get_lines(["Expense"])

        revenue_lines = [{"account_code": r["account__code"],
                          "account_name": r["account__name"],
                          "amount": _net(r, "credit")} for r in revenue_rows]
        expense_lines = [{"account_code": r["account__code"],
                          "account_name": r["account__name"],
                          "amount": _net(r, "debit")} for r in expense_rows]

        # Split expenses into COGS vs operating
        cogs_codes = {"5000"}  # extend as needed
        cogs_lines = [l for l in expense_lines if l["account_code"] in cogs_codes]
        opex_lines = [l for l in expense_lines if l["account_code"] not in cogs_codes]

        total_revenue = sum(l["amount"] for l in revenue_lines)
        total_cogs = sum(l["amount"] for l in cogs_lines)
        total_opex = sum(l["amount"] for l in opex_lines)
        gross_profit = total_revenue - total_cogs
        net_profit = gross_profit - total_opex

        return {
            "date_from": date_from,
            "date_to": date_to,
            "revenue": revenue_lines,
            "cost_of_sales": cogs_lines,
            "operating_expenses": opex_lines,
            "total_revenue": total_revenue,
            "total_cost_of_sales": total_cogs,
            "gross_profit": gross_profit,
            "total_operating_expenses": total_opex,
            "net_profit": net_profit,
        }

    # ------------------------------------------------------------------ #
    # Balance Sheet                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def balance_sheet(company: Company, as_of_date: date) -> dict:
        def _balances(account_types):
            rows = (
                JournalEntryLine.objects.filter(
                    journal_entry__company=company,
                    journal_entry__entry_date__lte=as_of_date,
                    journal_entry__is_balanced=True,
                    account__account_type__in=account_types,
                )
                .values("account__code", "account__name", "account__account_type")
                .annotate(total_debits=Sum("debit"), total_credits=Sum("credit"))
                .order_by("account__code")
            )
            result = []
            for r in rows:
                dr = r["total_debits"] or Decimal("0")
                cr = r["total_credits"] or Decimal("0")
                acct_type = r["account__account_type"].lower()
                balance = dr - cr if acct_type in ("asset",) else cr - dr
                result.append({
                    "account_code": r["account__code"],
                    "account_name": r["account__name"],
                    "balance": balance,
                })
            return result

        assets = _balances(["Asset"])
        liabilities = _balances(["Liability"])
        equity = _balances(["Equity"])

        total_assets = sum(r["balance"] for r in assets)
        total_liabilities = sum(r["balance"] for r in liabilities)
        total_equity = sum(r["balance"] for r in equity)

        return {
            "as_of_date": as_of_date,
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            "is_balanced": abs(total_assets - (total_liabilities + total_equity)) < Decimal("0.01"),
        }

    # ------------------------------------------------------------------ #
    # AR Aging                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def ar_aging(company: Company) -> list:
        today = timezone.now().date()
        records = (
            AccountsReceivable.objects.filter(
                invoice__sales_order__warehouse__company=company,
            )
            .exclude(status="paid")
            .select_related("customer")
        )

        customer_map = {}
        for ar in records:
            cid = ar.customer_id
            if cid not in customer_map:
                customer_map[cid] = {
                    "customer_id": cid,
                    "customer_name": ar.customer.name,
                    "current": Decimal("0"),
                    "days_1_30": Decimal("0"),
                    "days_31_60": Decimal("0"),
                    "days_61_90": Decimal("0"),
                    "over_90": Decimal("0"),
                    "total_outstanding": Decimal("0"),
                }
            days = (today - ar.due_date).days
            amt = ar.amount_outstanding
            row = customer_map[cid]
            row["total_outstanding"] += amt
            if days <= 0:
                row["current"] += amt
            elif days <= 30:
                row["days_1_30"] += amt
            elif days <= 60:
                row["days_31_60"] += amt
            elif days <= 90:
                row["days_61_90"] += amt
            else:
                row["over_90"] += amt

        return list(customer_map.values())

    # ------------------------------------------------------------------ #
    # AP Aging                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def ap_aging(company: Company) -> list:
        today = timezone.now().date()
        records = (
            AccountsPayable.objects.filter(
                supplier_invoice__warehouse__company=company,
            )
            .exclude(status="paid")
            .select_related("supplier")
        )

        supplier_map = {}
        for ap in records:
            sid = ap.supplier_id
            if sid not in supplier_map:
                supplier_map[sid] = {
                    "supplier_id": sid,
                    "supplier_name": ap.supplier.name,
                    "current": Decimal("0"),
                    "days_1_30": Decimal("0"),
                    "days_31_60": Decimal("0"),
                    "days_61_90": Decimal("0"),
                    "over_90": Decimal("0"),
                    "total_outstanding": Decimal("0"),
                }
            days = (today - ap.due_date).days
            amt = ap.amount_outstanding
            row = supplier_map[sid]
            row["total_outstanding"] += amt
            if days <= 0:
                row["current"] += amt
            elif days <= 30:
                row["days_1_30"] += amt
            elif days <= 60:
                row["days_31_60"] += amt
            elif days <= 90:
                row["days_61_90"] += amt
            else:
                row["over_90"] += amt

        return list(supplier_map.values())
