from dataclasses import dataclass
from typing import Iterable

from django.core.management.base import BaseCommand, CommandError

from apps.accounting.models import BankAccount
from apps.finance.models import CustomerPayment, SupplierPayment
from apps.sales.models import Payment as SalesPayment
from central.models import Company


@dataclass
class BackfillCounters:
    scanned: int = 0
    updated: int = 0
    skipped: int = 0


class Command(BaseCommand):
    help = (
        "Backfill missing bank_account links on sales and finance payment records. "
        "Runs in dry-run mode unless --apply is provided."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist changes. Without this flag, command reports what would change.",
        )
        parser.add_argument(
            "--company-id",
            type=str,
            help="Optional company UUID filter.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        company_id = options.get("company_id")

        companies = Company.objects.all().order_by("name")
        if company_id:
            companies = companies.filter(id=company_id)
            if not companies.exists():
                raise CommandError(f"Company not found for id: {company_id}")

        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.NOTICE(f"Running backfill in {mode} mode"))

        grand = {
            "sales": BackfillCounters(),
            "customer": BackfillCounters(),
            "supplier": BackfillCounters(),
        }

        for company in companies:
            accounts = list(
                BankAccount.objects.filter(
                    company=company, is_active=True
                ).select_related("coa_account")
            )
            if not accounts:
                self.stdout.write(
                    self.style.WARNING(
                        f"[{company.name}] no active bank accounts found, skipping."
                    )
                )
                continue

            self.stdout.write(f"[{company.name}] active bank accounts: {len(accounts)}")

            sales = self._backfill_sales(company, accounts, apply_changes)
            customer = self._backfill_customer(company, accounts, apply_changes)
            supplier = self._backfill_supplier(company, accounts, apply_changes)

            grand["sales"].scanned += sales.scanned
            grand["sales"].updated += sales.updated
            grand["sales"].skipped += sales.skipped

            grand["customer"].scanned += customer.scanned
            grand["customer"].updated += customer.updated
            grand["customer"].skipped += customer.skipped

            grand["supplier"].scanned += supplier.scanned
            grand["supplier"].updated += supplier.updated
            grand["supplier"].skipped += supplier.skipped

            self.stdout.write(
                f"[{company.name}] sales={sales.updated}/{sales.scanned}, "
                f"customer={customer.updated}/{customer.scanned}, "
                f"supplier={supplier.updated}/{supplier.scanned}"
            )

        self.stdout.write(self.style.SUCCESS("Backfill summary"))
        self.stdout.write(
            f"sales: updated={grand['sales'].updated}, scanned={grand['sales'].scanned}, skipped={grand['sales'].skipped}"
        )
        self.stdout.write(
            f"customer: updated={grand['customer'].updated}, scanned={grand['customer'].scanned}, skipped={grand['customer'].skipped}"
        )
        self.stdout.write(
            f"supplier: updated={grand['supplier'].updated}, scanned={grand['supplier'].scanned}, skipped={grand['supplier'].skipped}"
        )

        if not apply_changes:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run only. Re-run with --apply to persist the assignments."
                )
            )

    def _pick_default(
        self,
        payment_method: str,
        accounts: Iterable[BankAccount],
    ) -> BankAccount | None:
        accounts = list(accounts)
        if not accounts:
            return None

        # Prefer cash account for cash-like methods; otherwise prefer current/savings.
        if payment_method in {"cash", "mobile_money"}:
            for account in accounts:
                if account.account_type == "cash":
                    return account
            return accounts[0]

        for account in accounts:
            if account.account_type in {"current", "savings"}:
                return account
        return accounts[0]

    def _backfill_sales(
        self,
        company: Company,
        accounts: list[BankAccount],
        apply_changes: bool,
    ) -> BackfillCounters:
        counters = BackfillCounters()
        qs = SalesPayment.objects.filter(
            invoice__sales_order__warehouse__company=company,
            bank_account__isnull=True,
        ).select_related("invoice__sales_order__warehouse")

        for payment in qs.iterator():
            counters.scanned += 1
            selected = self._pick_default(payment.payment_method, accounts)
            if not selected:
                counters.skipped += 1
                continue

            if apply_changes:
                payment.bank_account = selected
                payment.save(update_fields=["bank_account"])
            counters.updated += 1

        return counters

    def _backfill_customer(
        self,
        company: Company,
        accounts: list[BankAccount],
        apply_changes: bool,
    ) -> BackfillCounters:
        counters = BackfillCounters()
        qs = CustomerPayment.objects.filter(
            accounts_receivable__invoice__sales_order__warehouse__company=company,
            bank_account__isnull=True,
        ).select_related("sales_payment", "accounts_receivable__invoice")

        for payment in qs.iterator():
            counters.scanned += 1
            selected = None
            if payment.sales_payment and payment.sales_payment.bank_account_id:
                selected = payment.sales_payment.bank_account
            if not selected:
                selected = self._pick_default(payment.payment_method, accounts)
            if not selected:
                counters.skipped += 1
                continue

            if apply_changes:
                payment.bank_account = selected
                payment.save(update_fields=["bank_account"])
            counters.updated += 1

        return counters

    def _backfill_supplier(
        self,
        company: Company,
        accounts: list[BankAccount],
        apply_changes: bool,
    ) -> BackfillCounters:
        counters = BackfillCounters()
        qs = SupplierPayment.objects.filter(
            accounts_payable__supplier_invoice__warehouse__company=company,
            bank_account__isnull=True,
        ).select_related("accounts_payable__supplier_invoice__warehouse")

        for payment in qs.iterator():
            counters.scanned += 1
            selected = self._pick_default(payment.payment_method, accounts)
            if not selected:
                counters.skipped += 1
                continue

            if apply_changes:
                payment.bank_account = selected
                payment.save(update_fields=["bank_account"])
            counters.updated += 1

        return counters
