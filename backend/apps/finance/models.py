"""
Finance module models.

AccountsReceivable  — tracks customer debt (one per sales invoice)
AccountsPayable     — tracks supplier debt (one per supplier invoice)
SupplierPayment     — records money going out to suppliers

All three are created/updated automatically by their respective modules.
No manual creation by users.
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.accounting.models import JournalEntry
from apps.purchasing.models import Supplier, SupplierInvoice
from apps.sales.models import Customer, Invoice as SalesInvoice


class AccountsReceivable(models.Model):
    """
    Tracks money owed to the company by customers.
    One record per sales invoice. Created when an invoice is issued.
    Updated as payments come in.
    """

    STATUS_CHOICES = [
        ("open", "Open"),
        ("partially_paid", "Partially Paid"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="accounts_receivable"
    )
    invoice = models.OneToOneField(
        SalesInvoice, on_delete=models.PROTECT, related_name="ar_record"
    )
    original_amount = models.DecimalField(max_digits=14, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_outstanding = models.DecimalField(max_digits=14, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="ar_records",
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Accounts Receivable"
        verbose_name_plural = "Accounts Receivable"
        indexes = [
            models.Index(fields=["customer", "status"], name="ar_customer_status_idx"),
            models.Index(fields=["due_date", "status"], name="ar_due_date_status_idx"),
        ]

    def __str__(self):
        return f"AR — {self.customer.name} | {self.invoice.invoice_number} | {self.status}"


class AccountsPayable(models.Model):
    """
    Tracks money owed by the company to suppliers.
    One record per supplier invoice. Created when a GRN is confirmed.
    Updated as supplier payments are recorded.
    """

    STATUS_CHOICES = [
        ("open", "Open"),
        ("partially_paid", "Partially Paid"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="accounts_payable"
    )
    supplier_invoice = models.OneToOneField(
        SupplierInvoice, on_delete=models.PROTECT, related_name="ap_record"
    )
    original_amount = models.DecimalField(max_digits=14, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_outstanding = models.DecimalField(max_digits=14, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="ap_records",
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Accounts Payable"
        verbose_name_plural = "Accounts Payable"
        indexes = [
            models.Index(fields=["supplier", "status"], name="ap_supplier_status_idx"),
            models.Index(fields=["due_date", "status"], name="ap_due_date_status_idx"),
        ]

    def __str__(self):
        return f"AP — {self.supplier.name} | {self.supplier_invoice.invoice_number} | {self.status}"


class SupplierPayment(models.Model):
    """
    Records money going out to suppliers.
    Creating a payment triggers a JournalEntry: Debit AP, Credit Cash.
    Updates AccountsPayable.amount_paid and recomputes amount_outstanding.
    """

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
        ("cheque", "Cheque"),
        ("mobile_money", "Mobile Money"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    accounts_payable = models.ForeignKey(
        AccountsPayable, on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateTimeField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    reference = models.CharField(max_length=255, blank=True)
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="supplier_payments",
        null=True, blank=True,
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="supplier_payments_made",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Supplier Payment"
        verbose_name_plural = "Supplier Payments"
        indexes = [
            models.Index(fields=["accounts_payable", "payment_date"], name="sp_ap_date_idx"),
        ]

    def __str__(self):
        return (
            f"Payment {self.amount} to "
            f"{self.accounts_payable.supplier.name} on {self.payment_date:%Y-%m-%d}"
        )
