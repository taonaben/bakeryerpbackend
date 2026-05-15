from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.costing.models import OverheadRate
from apps.costing.services.costing_engine import CostingEngine
from apps.costing.services.standard_cost_engine import WarehouseStandardCostEngine
from apps.formulation.models import Formula, FormulaLine
from apps.production.models import BatchMaterial, BatchOutput, ProductionBatch, ProductionOrder
from apps.purchasing.models import Supplier, SupplierProduct
from central.models import Company, Product, Warehouse


class LaborMinuteOverheadTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Bake Co")
        self.user = get_user_model().objects.create_user(
            username="costing-manager",
            email="costing@example.com",
            password="password",
            role="manager",
            company=self.company,
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            name="Main Production",
            wh_type="production",
        )
        self.finished_product = Product.objects.create(
            company=self.company,
            name="Bread",
            category="Bakery",
            unit_of_measure="pieces",
        )
        self.material_product = Product.objects.create(
            company=self.company,
            name="Flour",
            category="Raw Material",
            unit_of_measure="kg",
        )
        self.supplier = Supplier.objects.create(
            company=self.company,
            name="Flour Supplier",
            primary_email="supplier@example.com",
            primary_phone="123456",
            currency="USD",
        )
        SupplierProduct.objects.create(
            supplier=self.supplier,
            product=self.material_product,
            price=Decimal("2.00"),
            lead_time_days=1,
            is_preferred=True,
            is_active=True,
        )

    def _formula(self, *, labor_minutes_per_batch=None):
        formula = Formula.objects.create(
            name="Bread Formula",
            product=self.finished_product,
            revision=1,
            batch_size=100,
            yield_percentage=80,
            labor_minutes_per_batch=labor_minutes_per_batch,
            status="active",
            is_active=True,
        )
        FormulaLine.objects.create(
            formula=formula,
            sequence=1,
            line_type="MATERIAL",
            product=self.material_product,
            quantity=40,
        )
        return formula

    def _overhead_rate(self, *, planned_labor_minutes=None):
        return OverheadRate.objects.create(
            warehouse=self.warehouse,
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            total_overhead_budgeted=Decimal("1200.00"),
            planned_production_units=Decimal("1000.0000"),
            planned_labor_minutes=planned_labor_minutes,
            currency="USD",
            created_by=self.user,
        )

    def test_overhead_rate_computes_labor_minute_rate_and_unit_rate(self):
        rate = self._overhead_rate(planned_labor_minutes=Decimal("2400.0000"))

        self.assertEqual(rate.rate_per_unit, Decimal("1.200000"))
        self.assertEqual(rate.rate_per_labor_minute, Decimal("0.500000"))

    def test_standard_cost_uses_labor_minutes_and_effective_units(self):
        formula = self._formula(labor_minutes_per_batch=Decimal("160.0000"))
        self._overhead_rate(planned_labor_minutes=Decimal("2400.0000"))

        standard_cost = WarehouseStandardCostEngine(
            formula=formula,
            computed_by=self.user,
            warehouse=self.warehouse,
        ).run()

        self.assertEqual(standard_cost.overhead_allocation_method, "labor_minutes")
        self.assertEqual(standard_cost.material_cost_per_unit, Decimal("1.00"))
        self.assertEqual(standard_cost.overhead_cost_per_unit, Decimal("1.00000000"))
        self.assertEqual(standard_cost.total_standard_cost_per_unit, Decimal("2.00000000"))

    def test_standard_cost_falls_back_to_unit_rate_without_formula_labor_minutes(self):
        formula = self._formula()
        self._overhead_rate(planned_labor_minutes=Decimal("2400.0000"))

        standard_cost = WarehouseStandardCostEngine(
            formula=formula,
            computed_by=self.user,
            warehouse=self.warehouse,
        ).run()

        self.assertEqual(standard_cost.overhead_allocation_method, "unit_rate")
        self.assertEqual(standard_cost.overhead_cost_per_unit, Decimal("1.200000"))

    def test_actual_costing_uses_labor_minutes_scaled_to_actual_output(self):
        formula = self._formula(labor_minutes_per_batch=Decimal("160.0000"))
        self._overhead_rate(planned_labor_minutes=Decimal("2400.0000"))
        standard_cost = WarehouseStandardCostEngine(
            formula=formula,
            computed_by=self.user,
            warehouse=self.warehouse,
        ).run()
        order = ProductionOrder.objects.create(
            product=self.finished_product,
            quantity=50,
            warehouse=self.warehouse,
            formula=formula,
            status="scheduled",
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now(),
        )
        batch = ProductionBatch.objects.create(
            production_order=order,
            batch_number="PB-LABOR",
            quantity_produced=40,
            status="completed",
            completed_at=timezone.now(),
        )
        BatchMaterial.objects.create(
            production_batch=batch,
            product=self.material_product,
            quantity_used=Decimal("20.0000"),
        )
        BatchOutput.objects.create(
            production_batch=batch,
            product=self.finished_product,
            quantity_produced=Decimal("40.0000"),
        )

        entry = CostingEngine(batch).run()

        self.assertEqual(entry.standard_cost_id, standard_cost.id)
        self.assertEqual(entry.overhead_allocation_method, "labor_minutes")
        self.assertEqual(entry.overhead_cost, Decimal("40.00"))

    def test_actual_costing_falls_back_to_unit_rate_without_formula_labor_minutes(self):
        formula = self._formula()
        self._overhead_rate(planned_labor_minutes=Decimal("2400.0000"))
        WarehouseStandardCostEngine(
            formula=formula,
            computed_by=self.user,
            warehouse=self.warehouse,
        ).run()
        order = ProductionOrder.objects.create(
            product=self.finished_product,
            quantity=50,
            warehouse=self.warehouse,
            formula=formula,
            status="scheduled",
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now(),
        )
        batch = ProductionBatch.objects.create(
            production_order=order,
            batch_number="PB-UNIT",
            quantity_produced=40,
            status="completed",
            completed_at=timezone.now(),
        )
        BatchMaterial.objects.create(
            production_batch=batch,
            product=self.material_product,
            quantity_used=Decimal("20.0000"),
        )
        BatchOutput.objects.create(
            production_batch=batch,
            product=self.finished_product,
            quantity_produced=Decimal("40.0000"),
        )

        entry = CostingEngine(batch).run()

        self.assertEqual(entry.overhead_allocation_method, "unit_rate")
        self.assertEqual(entry.overhead_cost, Decimal("48.00"))
