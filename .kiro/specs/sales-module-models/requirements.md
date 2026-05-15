# Requirements Document

## Introduction

The sales module provides the data layer for the full lifecycle of goods leaving inventory and reaching customers. It covers two workflows: a fast POS flow for retail/walk-in sales and a multi-step B2B flow for business customers with credit terms, partial deliveries, and formal invoicing. This document defines the eight Django models — Customer, CustomerProduct, SalesOrder, SalesOrderLine, Delivery, DeliveryLine, Invoice, and Payment — their fields, constraints, and relationships.

## Glossary

- **Customer**: A buyer entity, either a retail walk-in or a registered business.
- **CustomerProduct**: A negotiated pricing agreement between the company and a specific business customer for a specific product.
- **SalesOrder**: The header record for any sale, owning the status lifecycle and aggregated financial totals.
- **SalesOrderLine**: One line per product on a SalesOrder, tracking ordered and dispatched quantities.
- **Delivery**: The physical dispatch record linked to a SalesOrder; a single order may have multiple deliveries.
- **DeliveryLine**: The specific product, batch, and quantity within a Delivery; drives stock movement and batch traceability.
- **Invoice**: The financial document sent to the customer — a receipt for POS or a tax invoice for B2B.
- **Payment**: A record of money received against an Invoice; supports partial payments.
- **POS**: Point-of-sale order type for retail/walk-in transactions.
- **B2B**: Business-to-business order type for registered business customers with credit terms.
- **StockMovement**: An inventory record created when goods leave the warehouse (type=SALE, direction=OUT).
- **CostingEntry**: The source of cost-per-unit data used to snapshot COGS at dispatch time.
- **ProductPricingRule**: Defines the minimum selling price floor for a product.
- **Batch**: A production batch record used for traceability of dispatched goods.
- **COGS**: Cost of Goods Sold — `quantity_dispatched × cost_per_unit`.

---

## Requirements

### Requirement 1: Customer Model

**User Story:** As a sales operator, I want to store customer records with type-specific fields, so that I can manage both retail walk-ins and registered business accounts in a single model.

#### Acceptance Criteria

1. THE Customer model SHALL store the following fields: `id` (UUID, primary key), `customer_type` (choices: retail, business), `name`, `phone`, `email`, `address`, `company_name`, `payment_terms` (choices: cash, net_30, net_60), `credit_limit`, `tax_number`, `is_active`, `created_at`.
2. WHEN a Customer record is created, THE Customer model SHALL assign a UUID as the primary key.
3. THE Customer model SHALL require `name` to be non-empty.
4. THE Customer model SHALL default `payment_terms` to `cash` and default `is_active` to `True`.
5. WHILE `customer_type` is `retail`, THE Customer model SHALL treat `credit_limit`, `company_name`, and `tax_number` as optional fields with no enforcement.
6. WHILE `customer_type` is `business`, THE Customer model SHALL allow `credit_limit`, `company_name`, `tax_number`, and `payment_terms` to be set and enforced.

---

### Requirement 2: CustomerProduct (Pricing Agreement) Model

**User Story:** As a sales manager, I want to record negotiated unit prices per customer per product, so that B2B orders can reference agreed pricing.

#### Acceptance Criteria

1. THE CustomerProduct model SHALL store the following fields: `id` (UUID, primary key), `customer` (FK to Customer), `product` (FK to Product), `unit_price`, `min_order_quantity`, `is_active`, `valid_from`, `valid_until`, `created_at`.
2. WHEN a CustomerProduct record is saved with `unit_price` below `ProductPricingRule.minimum_selling_price` for that product, THE CustomerProduct model SHALL flag the violation as a warning.
3. THE CustomerProduct model SHALL only be created for customers with `customer_type=business`.
4. THE CustomerProduct model SHALL protect the referenced `Product` from deletion while an agreement exists.
5. WHEN a CustomerProduct record is deleted, THE CustomerProduct model SHALL cascade-delete from the parent Customer.

---

### Requirement 3: SalesOrder Model

**User Story:** As a sales operator, I want a header record for each sale that tracks status, financial totals, and order type, so that I can manage both POS and B2B orders through their full lifecycle.

#### Acceptance Criteria

1. THE SalesOrder model SHALL store the following fields: `id` (UUID, primary key), `order_number` (unique, auto-generated), `customer` (FK to Customer), `warehouse` (FK to Warehouse), `order_type` (choices: pos, b2b), `status` (choices: draft, confirmed, picking, dispatched, invoiced, paid, cancelled), `order_date`, `expected_delivery_date`, `delivery_address`, `notes`, `subtotal`, `tax_amount`, `total_amount`, `created_by` (FK to User), `created_at`, `updated_at`.
2. WHEN a SalesOrder is created, THE SalesOrder model SHALL auto-generate `order_number` in the format `SO-XXXXX` (sequential, zero-padded to 5 digits).
3. WHEN `order_type` is `pos`, THE SalesOrder model SHALL only permit the status transition `draft → dispatched`.
4. WHEN `order_type` is `b2b`, THE SalesOrder model SHALL only permit the status transitions `draft → confirmed → picking → dispatched → invoiced → paid`.
5. WHEN a SalesOrder `status` is `dispatched`, `invoiced`, or `paid`, THE SalesOrder model SHALL reject any attempt to set `status=cancelled`.
6. THE SalesOrder model SHALL maintain `subtotal`, `tax_amount`, and `total_amount` as denormalized aggregates that reflect the sum of all associated SalesOrderLine values.
7. THE SalesOrder model SHALL default `status` to `draft` and default `subtotal`, `tax_amount`, `total_amount` to `0`.

---

### Requirement 4: SalesOrderLine Model

**User Story:** As a sales operator, I want each order line to track ordered quantity, unit price, dispatched quantity, and cost data, so that I can support partial fulfilment and COGS reporting.

#### Acceptance Criteria

1. THE SalesOrderLine model SHALL store the following fields: `id` (UUID, primary key), `sales_order` (FK to SalesOrder), `product` (FK to Product), `quantity`, `unit_price`, `subtotal`, `quantity_dispatched`, `cost_per_unit`, `cogs_total`.
2. WHEN a SalesOrderLine is saved, THE SalesOrderLine model SHALL compute `subtotal = quantity × unit_price`.
3. WHEN the parent SalesOrder `status` moves past `draft`, THE SalesOrderLine model SHALL prevent any change to `unit_price`.
4. THE SalesOrderLine model SHALL ensure `quantity_dispatched` never exceeds `quantity`.
5. WHEN a SalesOrder is dispatched, THE SalesOrderLine model SHALL populate `cost_per_unit` from the corresponding `CostingEntry` record.
6. THE SalesOrderLine model SHALL compute `cogs_total = quantity_dispatched × cost_per_unit` whenever `cost_per_unit` is set.
7. THE SalesOrderLine model SHALL default `quantity_dispatched` to `0`.

---

### Requirement 5: Delivery Model

**User Story:** As a warehouse operator, I want a delivery record per physical dispatch, so that I can track multiple partial deliveries against a single B2B order and manage delivery status.

#### Acceptance Criteria

1. THE Delivery model SHALL store the following fields: `id` (UUID, primary key), `sales_order` (FK to SalesOrder), `warehouse` (FK to Warehouse), `delivery_number` (unique, auto-generated), `status` (choices: pending, in_transit, delivered, failed), `dispatched_at`, `delivered_at`, `driver_name`, `vehicle`, `notes`, `created_by` (FK to User).
2. WHEN a Delivery is created, THE Delivery model SHALL auto-generate `delivery_number` in the format `DEL-XXXXX` (sequential, zero-padded to 5 digits).
3. THE Delivery model SHALL default `status` to `pending`.
4. WHEN a Delivery `status` is `failed`, THE Delivery model SHALL prevent the parent SalesOrder from transitioning to `invoiced` or `paid`.
5. THE Delivery model SHALL protect the referenced SalesOrder from deletion while a Delivery record exists.

---

### Requirement 6: DeliveryLine Model

**User Story:** As a warehouse operator, I want each delivery line to record the exact product, batch, and quantity dispatched, so that every stock movement is traceable to a production batch.

#### Acceptance Criteria

1. THE DeliveryLine model SHALL store the following fields: `id` (UUID, primary key), `delivery` (FK to Delivery), `sales_order_line` (FK to SalesOrderLine), `product` (FK to Product, denormalized), `batch` (FK to Batch), `quantity_delivered`.
2. THE DeliveryLine model SHALL require `batch` to be non-null — anonymous stock movements are not permitted.
3. WHEN a DeliveryLine is created, THE DeliveryLine model SHALL post a StockMovement record with `type=SALE` and direction `OUT`.
4. WHEN a DeliveryLine is created, THE DeliveryLine model SHALL increment `SalesOrderLine.quantity_dispatched` by `quantity_delivered`.
5. THE DeliveryLine model SHALL ensure `quantity_delivered` does not exceed the remaining undelivered quantity on the associated SalesOrderLine (`SalesOrderLine.quantity − SalesOrderLine.quantity_dispatched`).
6. THE DeliveryLine model SHALL protect the referenced Batch and SalesOrderLine from deletion while a DeliveryLine record exists.

---

### Requirement 7: Invoice Model

**User Story:** As a finance operator, I want an invoice record linked to each sales order, so that I can issue receipts for POS sales and tax invoices for B2B sales with correct due dates and immutable amounts.

#### Acceptance Criteria

1. THE Invoice model SHALL store the following fields: `id` (UUID, primary key), `sales_order` (OneToOne FK to SalesOrder), `invoice_number` (unique, auto-generated), `invoice_type` (choices: receipt, tax_invoice), `issued_date`, `due_date`, `subtotal`, `tax_amount`, `total_amount`, `status` (choices: draft, issued, partially_paid, paid, overdue, cancelled), `created_by` (FK to User), `created_at`.
2. WHEN an Invoice is created, THE Invoice model SHALL auto-generate `invoice_number` in the format `INV-XXXXX` (sequential, zero-padded to 5 digits).
3. WHEN an Invoice is created, THE Invoice model SHALL compute `due_date` based on `sales_order.customer.payment_terms`: `cash` → same as `issued_date`; `net_30` → `issued_date + 30 days`; `net_60` → `issued_date + 60 days`.
4. WHEN Invoice `status` is `issued`, THE Invoice model SHALL prevent any change to `subtotal`, `tax_amount`, or `total_amount`.
5. WHEN the parent SalesOrder `order_type` is `pos`, THE Invoice model SHALL set `invoice_type` to `receipt`.
6. WHEN the parent SalesOrder `order_type` is `b2b`, THE Invoice model SHALL set `invoice_type` to `tax_invoice`.
7. THE Invoice model SHALL default `status` to `draft`.

---

### Requirement 8: Payment Model

**User Story:** As a finance operator, I want to record payments received against invoices, so that I can track partial and full payment status for both POS and B2B orders.

#### Acceptance Criteria

1. THE Payment model SHALL store the following fields: `id` (UUID, primary key), `invoice` (FK to Invoice), `customer` (FK to Customer, denormalized), `amount`, `payment_method` (choices: cash, bank_transfer, mobile_money, cheque), `payment_date`, `reference`, `received_by` (FK to User), `notes`.
2. THE Payment model SHALL require `amount` to be greater than zero.
3. WHEN a Payment is saved and `SUM(invoice.payments.amount) == invoice.total_amount`, THE Payment model SHALL set `invoice.status` to `paid`.
4. WHEN a Payment is saved and `0 < SUM(invoice.payments.amount) < invoice.total_amount`, THE Payment model SHALL set `invoice.status` to `partially_paid`.
5. IF a Payment is saved and `SUM(invoice.payments.amount) > invoice.total_amount`, THEN THE Payment model SHALL reject the payment with a validation error indicating overpayment.
6. THE Payment model SHALL protect the referenced Invoice and Customer from deletion while a Payment record exists.

---

### Requirement 9: Reference Number Generation

**User Story:** As a system administrator, I want all reference numbers to be auto-generated with consistent formats, so that records are uniquely and predictably identifiable.

#### Acceptance Criteria

1. THE SalesOrder model SHALL generate `order_number` values that are unique across all SalesOrder records.
2. THE Delivery model SHALL generate `delivery_number` values that are unique across all Delivery records.
3. THE Invoice model SHALL generate `invoice_number` values that are unique across all Invoice records.
4. WHEN multiple records are created concurrently, THE reference number generator SHALL produce no duplicate values.

---

### Requirement 10: Cross-Model Referential Integrity

**User Story:** As a developer, I want foreign key constraints and cascade rules to be correctly defined, so that data integrity is maintained across all sales module models.

#### Acceptance Criteria

1. THE SalesOrder model SHALL use `on_delete=PROTECT` for Customer and Warehouse foreign keys.
2. THE SalesOrderLine model SHALL use `on_delete=CASCADE` for the SalesOrder foreign key and `on_delete=PROTECT` for the Product foreign key.
3. THE Delivery model SHALL use `on_delete=PROTECT` for SalesOrder and Warehouse foreign keys.
4. THE DeliveryLine model SHALL use `on_delete=CASCADE` for the Delivery foreign key and `on_delete=PROTECT` for SalesOrderLine, Product, and Batch foreign keys.
5. THE Invoice model SHALL use `on_delete=PROTECT` for the SalesOrder foreign key.
6. THE Payment model SHALL use `on_delete=PROTECT` for Invoice and Customer foreign keys.
7. THE CustomerProduct model SHALL use `on_delete=CASCADE` for the Customer foreign key and `on_delete=PROTECT` for the Product foreign key.
