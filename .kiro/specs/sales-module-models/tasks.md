# Implementation Plan: Sales Module Models

## Overview

Scaffold the `apps/sales` Django app and implement the eight data models — Customer, CustomerProduct, SalesOrder, SalesOrderLine, Delivery, DeliveryLine, Invoice, Payment — along with migrations, admin registration, and property-based tests using `hypothesis`. No business logic, services, signals, or views are in scope.

## Tasks

- [x] 1. Scaffold the sales app
  - Create `backend/apps/sales/` with `__init__.py`, `apps.py`, `models.py`, `admin.py`, `migrations/__init__.py`
  - In `apps.py` set `name = "apps.sales"` and `default_auto_field = "django.db.models.BigAutoField"`
  - Add `"apps.sales"` to `INSTALLED_APPS` in the Django settings file
  - _Requirements: 1.1, 3.1, 5.1, 7.1, 8.1_

- [x] 2. Implement the Customer model
  - [x] 2.1 Write the `Customer` model in `backend/apps/sales/models.py`
    - UUID primary key, `customer_type` choices (retail/business), `name`, `phone`, `email`, `address`, `company_name`, `payment_terms` (default `cash`), `credit_limit`, `tax_number`, `is_active` (default `True`), `created_at`
    - Add `Meta` with `verbose_name`, `indexes` on `customer_type` and `is_active`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 2.2 Write unit tests for Customer
    - Test UUID PK assignment, `name` required, `payment_terms` default, `is_active` default
    - _Requirements: 1.2, 1.3, 1.4_

- [x] 3. Implement the CustomerProduct model
  - [x] 3.1 Write the `CustomerProduct` model
    - UUID PK, FK to `Customer` (`CASCADE`), FK to `Product` (`PROTECT`), `unit_price`, `min_order_quantity`, `is_active`, `valid_from`, `valid_until`, `created_at`
    - Add `clean()` to flag `unit_price < ProductPricingRule.minimum_selling_price` as a warning (non-blocking `ValidationError` with `code="price_below_floor"`)
    - Add `Meta` with index on `(customer, product)` and `(is_active, valid_from)`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 10.7_

  - [ ]* 3.2 Write property test for CustomerProduct price floor flag
    - **Property 9: CustomerProduct price floor flag**
    - **Validates: Requirements 2.2**
    - Generate arbitrary `unit_price` and `minimum_selling_price` values; assert `clean()` raises warning iff `unit_price < minimum_selling_price`

- [x] 4. Implement the reference number generator utility
  - [x] 4.1 Create `backend/apps/sales/utils.py` with a `generate_reference_number(prefix, model_class, field)` function
    - Use `SELECT MAX` + `F-expression` with `select_for_update()` inside a transaction to produce sequential, zero-padded 5-digit numbers (e.g. `SO-00001`)
    - _Requirements: 3.2, 5.2, 7.2, 9.1, 9.2, 9.3, 9.4_

  - [ ]* 4.2 Write property test for reference number format and uniqueness
    - **Property 5: Reference number format and uniqueness**
    - **Validates: Requirements 9.1, 9.2, 9.3**
    - Generate N reference numbers sequentially; assert each matches `^(SO|DEL|INV)-\d{5}$` and the full set has no duplicates

- [x] 5. Implement the SalesOrder model
  - [x] 5.1 Write the `SalesOrder` model
    - UUID PK, `order_number` (unique, editable=False), FK to `Customer` (`PROTECT`), FK to `Warehouse` (`PROTECT`), `order_type` choices (pos/b2b), `status` choices (draft/confirmed/picking/dispatched/invoiced/paid/cancelled, default `draft`), `order_date`, `expected_delivery_date`, `delivery_address`, `notes`, `subtotal`/`tax_amount`/`total_amount` (all default `0`), FK to `User` (`PROTECT`), `created_at`, `updated_at`
    - Override `save()` to call `generate_reference_number` when `order_number` is blank
    - Add `clean()` to enforce POS/B2B status transition rules and block cancellation after `dispatched`
    - Add `Meta` with indexes on `(status, order_type)`, `(customer, status)`, `(created_at,)`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 10.1_

  - [ ]* 5.2 Write property test for cancellation blocked after dispatch
    - **Property 7: Cancellation blocked after dispatch**
    - **Validates: Requirements 3.5**
    - For any `status` in `{dispatched, invoiced, paid}`, assert `clean()` raises `ValidationError` when `status=cancelled` is attempted

- [x] 6. Implement the SalesOrderLine model
  - [x] 6.1 Write the `SalesOrderLine` model
    - UUID PK, FK to `SalesOrder` (`CASCADE`), FK to `Product` (`PROTECT`), `quantity`, `unit_price`, `subtotal`, `quantity_dispatched` (default `0`), `cost_per_unit` (nullable), `cogs_total` (nullable)
    - Override `save()` to compute `subtotal = quantity × unit_price` and `cogs_total = quantity_dispatched × cost_per_unit` when `cost_per_unit` is set
    - Add `clean()` to lock `unit_price` once parent order is past `draft`, and to assert `quantity_dispatched <= quantity`
    - Add `Meta` with index on `(sales_order, product)`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 10.2_

  - [ ]* 6.2 Write property test for SalesOrderLine subtotal invariant
    - **Property 1: SalesOrderLine subtotal invariant**
    - **Validates: Requirements 4.2**
    - For any positive `quantity` and `unit_price`, assert `line.subtotal == quantity * unit_price` after save

  - [ ]* 6.3 Write property test for quantity_dispatched never exceeds quantity
    - **Property 2: quantity_dispatched never exceeds quantity**
    - **Validates: Requirements 4.4**
    - For any `quantity_dispatched > quantity`, assert `clean()` raises `ValidationError`

- [x] 7. Checkpoint — run migrations and verify models so far
  - Run `python manage.py makemigrations sales` and `python manage.py migrate`
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement the Delivery model
  - [x] 8.1 Write the `Delivery` model
    - UUID PK, FK to `SalesOrder` (`PROTECT`), FK to `Warehouse` (`PROTECT`), `delivery_number` (unique, editable=False), `status` choices (pending/in_transit/delivered/failed, default `pending`), `dispatched_at`, `delivered_at` (nullable), `driver_name` (nullable), `vehicle` (nullable), `notes` (nullable), FK to `User` (`PROTECT`)
    - Override `save()` to call `generate_reference_number` when `delivery_number` is blank
    - Add `Meta` with indexes on `(sales_order, status)`, `(status,)`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 10.3_

  - [ ]* 8.2 Write unit tests for Delivery
    - Test `delivery_number` format, default `status=pending`, PROTECT on SalesOrder FK
    - _Requirements: 5.2, 5.3, 5.5_

- [x] 9. Implement the DeliveryLine model
  - [x] 9.1 Write the `DeliveryLine` model
    - UUID PK, FK to `Delivery` (`CASCADE`), FK to `SalesOrderLine` (`PROTECT`), FK to `Product` (`PROTECT`), FK to `Batch` (`PROTECT`), `quantity_delivered`
    - Add `clean()` to assert `quantity_delivered <= (sales_order_line.quantity − sales_order_line.quantity_dispatched)`
    - Add `Meta` with index on `(delivery, sales_order_line)`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 10.4_

  - [ ]* 9.2 Write property test for DeliveryLine quantity_delivered respects remaining balance
    - **Property 3: DeliveryLine quantity_delivered respects remaining balance**
    - **Validates: Requirements 6.5**
    - For any `quantity_delivered` that would push the sum past `SalesOrderLine.quantity`, assert `clean()` raises `ValidationError`

- [x] 10. Implement the Invoice model
  - [x] 10.1 Write the `Invoice` model
    - UUID PK, OneToOne FK to `SalesOrder` (`PROTECT`), `invoice_number` (unique, editable=False), `invoice_type` choices (receipt/tax_invoice), `issued_date`, `due_date`, `subtotal`, `tax_amount`, `total_amount`, `status` choices (draft/issued/partially_paid/paid/overdue/cancelled, default `draft`), FK to `User` (`PROTECT`), `created_at`
    - Override `save()` to call `generate_reference_number` when `invoice_number` is blank, set `invoice_type` from `sales_order.order_type`, and compute `due_date` from `customer.payment_terms`
    - Add `clean()` to block changes to `subtotal`, `tax_amount`, `total_amount` when `status=issued`
    - Add `Meta` with indexes on `(status,)`, `(due_date, status)`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 10.5_

  - [ ]* 10.2 Write property test for Invoice due_date computation
    - **Property 6: Invoice due_date computation**
    - **Validates: Requirements 7.3**
    - For each of the three `payment_terms` values, assert `due_date` equals the expected offset from `issued_date`

- [x] 11. Implement the Payment model
  - [x] 11.1 Write the `Payment` model
    - UUID PK, FK to `Invoice` (`PROTECT`), FK to `Customer` (`PROTECT`), `amount`, `payment_method` choices (cash/bank_transfer/mobile_money/cheque), `payment_date`, `reference` (nullable), FK to `User` (`PROTECT`), `notes` (nullable)
    - Add `clean()` to assert `amount > 0` and to compute `SUM(invoice.payments.amount) + amount`; raise `ValidationError` on overpayment
    - Override `save()` to update `invoice.status` to `partially_paid` or `paid` after a successful payment
    - Add `Meta` with indexes on `(invoice, payment_date)`, `(customer,)`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 10.6_

  - [ ]* 11.2 Write property test for Payment sum drives invoice status correctly
    - **Property 4: Payment sum drives invoice status correctly**
    - **Validates: Requirements 8.3, 8.4, 8.5**
    - For any sequence of payment amounts against a fixed `invoice.total_amount`, assert: status is `partially_paid` when partial, `paid` when exact, and overpayment raises `ValidationError`

- [x] 12. Generate and apply migrations
  - Run `python manage.py makemigrations sales` to produce the initial migration file
  - Verify the migration file covers all 8 models with correct field types, constraints, and indexes
  - Run `python manage.py migrate` to apply
  - _Requirements: 1.1–8.1 (all models)_

- [ ] 13. Register all models in admin
  - In `backend/apps/sales/admin.py`, register `Customer`, `CustomerProduct`, `SalesOrder`, `SalesOrderLine`, `Delivery`, `DeliveryLine`, `Invoice`, `Payment` using `@admin.register`
  - Add `list_display`, `list_filter`, and `search_fields` for each model to make the admin usable
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1_

- [ ] 14. Final checkpoint — ensure all tests pass
  - Run the full test suite for the sales app: `python manage.py test apps.sales`
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The `generate_reference_number` utility (task 4.1) must be implemented before SalesOrder, Delivery, and Invoice models
- Property tests use `hypothesis` with `pytest-django`; add `@given` strategies from `hypothesis.strategies` and `hypothesis.extra.django`
- `DeliveryLine` side-effects (StockMovement creation, `quantity_dispatched` increment) are noted in the model constraints but the actual signal/service wiring is out of scope for this spec
- All `DecimalField` values for money use `max_digits=14, decimal_places=2`; cost/unit fields use `decimal_places=6`
