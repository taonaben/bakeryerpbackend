from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from central.models import Company, Warehouse, Product
from apps.formulation.models import Formula, FormulaLine
from apps.inventory.models import Batch, StockMovement, StockMovementBatch

from .models import (
    ProductionOrder,
    ProductionBatch,
    ProductionBatchLine,
    BatchMaterial,
    BatchOutput,
    BatchWaste,
    ReworkOrder,
)
from .services.production_engine import ProductionEngine
from .services.batch_service import ProductionBatchService
from .services.rework_service import ReworkService


class ProductionEngineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Test Co")
        self.warehouse = Warehouse.objects.create(
            company=self.company, name="Main Production", wh_type="production"
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
            category="Raw",
            unit_of_measure="kg",
        )

        self.formula = Formula.objects.create(
            name="Bread Formula",
            product=self.finished_product,
            revision=1,
            batch_size=10,
            yield_percentage=100,
            status="active",
        )

        FormulaLine.objects.create(
            formula=self.formula,
            sequence=1,
            line_type="MATERIAL",
            product=self.material_product,
            quantity=2,
        )
        FormulaLine.objects.create(
            formula=self.formula,
            sequence=2,
            line_type="INSTRUCTION",
            text="Mix ingredients",
        )

        self.order = ProductionOrder.objects.create(
            product=self.finished_product,
            quantity=20,
            warehouse=self.warehouse,
            formula=self.formula,
            status="scheduled",
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now(),
        )

    def test_start_production_creates_batch_and_movements(self):
        Batch.objects.create(
            product=self.material_product,
            warehouse=self.warehouse,
            quantity=10,
        )

        result = ProductionEngine.start_production(order_id=self.order.id)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "in_progress")
        self.assertEqual(ProductionBatch.objects.count(), 1)
        self.assertEqual(ProductionBatchLine.objects.count(), 2)
        self.assertEqual(BatchMaterial.objects.count(), 1)
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(StockMovementBatch.objects.count(), 1)

        batch = result["batch"]
        self.assertEqual(batch.quantity_produced, 20)

        stock_batch = Batch.objects.first()
        stock_batch.refresh_from_db()
        self.assertEqual(stock_batch.quantity, Decimal("6"))

    def test_start_production_with_selected_batches(self):
        batch_a = Batch.objects.create(
            product=self.material_product,
            warehouse=self.warehouse,
            quantity=3,
        )
        batch_b = Batch.objects.create(
            product=self.material_product,
            warehouse=self.warehouse,
            quantity=5,
        )

        selected_batches = [
            {
                "product_id": self.material_product.id,
                "batch_id": batch_a.id,
                "quantity": Decimal("2"),
            },
            {
                "product_id": self.material_product.id,
                "batch_id": batch_b.id,
                "quantity": Decimal("2"),
            },
        ]

        result = ProductionEngine.start_production(
            order_id=self.order.id,
            selected_batches=selected_batches,
        )

        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(StockMovementBatch.objects.count(), 2)

        movement = result["movements"][0]
        self.assertEqual(movement.total_quantity, Decimal("4"))

        batch_a.refresh_from_db()
        batch_b.refresh_from_db()
        self.assertEqual(batch_a.quantity, Decimal("1"))
        self.assertEqual(batch_b.quantity, Decimal("3"))

    def test_start_production_fails_on_shortage(self):
        Batch.objects.create(
            product=self.material_product,
            warehouse=self.warehouse,
            quantity=1,
        )

        with self.assertRaises(ValidationError):
            ProductionEngine.start_production(order_id=self.order.id)

    def test_finish_production_records_outputs_and_inventory(self):
        Batch.objects.create(
            product=self.material_product,
            warehouse=self.warehouse,
            quantity=10,
        )

        ProductionEngine.start_production(order_id=self.order.id)

        result = ProductionBatchService.finish_order(
            order_id=self.order.id,
            outputs=[
                {
                    "product": self.finished_product,
                    "quantity": Decimal("18"),
                }
            ],
            waste=[
                {
                    "product": self.finished_product,
                    "quantity": Decimal("2"),
                    "reason": "Burnt",
                }
            ],
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "completed")

        batch = result["batch"]
        batch.refresh_from_db()
        self.assertEqual(batch.status, "completed")
        self.assertIsNotNone(batch.completed_at)
        self.assertEqual(batch.quantity_produced, 18)

        self.assertEqual(BatchOutput.objects.count(), 1)
        self.assertEqual(BatchWaste.objects.count(), 1)

        movement = StockMovement.objects.filter(movement_type="IN").first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.total_quantity, Decimal("18"))
        self.assertEqual(
            StockMovementBatch.objects.filter(stock_movement=movement).count(), 1
        )

        finished_batch = Batch.objects.filter(product=self.finished_product).first()
        self.assertIsNotNone(finished_batch)
        finished_batch.refresh_from_db()
        self.assertEqual(finished_batch.quantity, Decimal("18"))


class ReworkServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Test Co")
        self.warehouse = Warehouse.objects.create(
            company=self.company, name="Main Production", wh_type="production"
        )

        self.product = Product.objects.create(
            company=self.company,
            name="Bread",
            category="Bakery",
            unit_of_measure="pieces",
        )

        self.input_batch = Batch.objects.create(
            product=self.product,
            warehouse=self.warehouse,
            quantity=10,
        )

        self.rework_order = ReworkOrder.objects.create(
            target_product=self.product,
            quantity_requested=8,
            warehouse=self.warehouse,
            status="scheduled",
            reason="Undercooked",
        )

    def test_start_rework_consumes_input_batches(self):
        result = ReworkService.start_rework(
            order_id=self.rework_order.id,
            inputs=[
                {
                    "batch_id": self.input_batch.id,
                    "quantity": Decimal("6"),
                }
            ],
        )

        self.rework_order.refresh_from_db()
        self.assertEqual(self.rework_order.status, "in_progress")
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(StockMovementBatch.objects.count(), 1)

        self.input_batch.refresh_from_db()
        self.assertEqual(self.input_batch.quantity, Decimal("4"))
        self.assertEqual(result["total_input"], Decimal("6"))

    def test_finish_rework_creates_output_batch(self):
        ReworkService.start_rework(
            order_id=self.rework_order.id,
            inputs=[
                {
                    "batch_id": self.input_batch.id,
                    "quantity": Decimal("6"),
                }
            ],
        )

        result = ReworkService.finish_rework(
            order_id=self.rework_order.id,
            outputs=[
                {
                    "product": self.product,
                    "quantity": Decimal("5"),
                }
            ],
        )

        self.rework_order.refresh_from_db()
        self.assertEqual(self.rework_order.status, "completed")
        self.assertIsNotNone(self.rework_order.completed_at)

        output_batch = (
            Batch.objects.filter(product=self.product).order_by("-created_at").first()
        )
        self.assertIsNotNone(output_batch)
        output_batch.refresh_from_db()
        self.assertEqual(output_batch.quantity, Decimal("5"))
        self.assertEqual(result["total_output"], Decimal("5"))

    def test_rework_consumed_flag_sets_on_full_consumption(self):
        ReworkService.start_rework(
            order_id=self.rework_order.id,
            inputs=[
                {
                    "batch_id": self.input_batch.id,
                    "quantity": Decimal("10"),
                }
            ],
        )

        self.input_batch.refresh_from_db()
        self.assertEqual(self.input_batch.quantity, Decimal("0"))
        self.assertTrue(self.input_batch.rework_consumed)

        self.assertEqual(result["expected_output"], Decimal("20"))
        self.assertEqual(result["expected_waste"], Decimal("0"))
        self.assertEqual(result["actual_output"], Decimal("18"))
        self.assertEqual(result["variance"], Decimal("2"))
