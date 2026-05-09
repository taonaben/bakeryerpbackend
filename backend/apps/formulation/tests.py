from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.formulation.models import Formula, FormulaLine
from apps.formulation.serializers import FormulaWriteSerializer
from apps.formulation.services.formula_services import FormulaService
from apps.production.services.production_planner import ProductionPlanner
from central.models import Company, Product


class FormulaModuleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Bake Co")
        self.finished_product = Product.objects.create(
            company=self.company,
            name="White Bread",
            category="Bakery",
            unit_of_measure="pieces",
        )
        self.flour = Product.objects.create(
            company=self.company,
            name="Flour",
            category="Raw Material",
            unit_of_measure="kg",
        )
        self.water = Product.objects.create(
            company=self.company,
            name="Water",
            category="Raw Material",
            unit_of_measure="l",
        )

    def test_create_formula_with_nested_lines(self):
        serializer = FormulaWriteSerializer(
            data={
                "name": "Bread Formula",
                "product": str(self.finished_product.id),
                "batch_size": 100,
                "yield_percentage": 95,
                "status": "draft",
                "lines": [
                    {
                        "sequence": 1,
                        "line_type": "MATERIAL",
                        "product": str(self.flour.id),
                        "quantity": 60,
                    },
                    {
                        "sequence": 2,
                        "line_type": "PROCESS",
                        "text": "Mix and rest dough.",
                    },
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        formula = serializer.save()

        self.assertEqual(formula.revision, 1)
        self.assertTrue(formula.is_active)
        self.assertFalse(formula.on_hold)
        self.assertEqual(formula.lines.count(), 2)

    def test_create_formula_assigns_next_product_revision(self):
        Formula.objects.create(
            name="Bread Formula Rev 1",
            product=self.finished_product,
            revision=1,
            batch_size=100,
            yield_percentage=95,
            status="active",
        )

        serializer = FormulaWriteSerializer(
            data={
                "name": "Bread Formula Rev 2",
                "product": str(self.finished_product.id),
                "revision": 99,
                "batch_size": 120,
                "yield_percentage": 96,
                "lines": [
                    {
                        "sequence": 1,
                        "line_type": "MATERIAL",
                        "product": str(self.flour.id),
                        "quantity": 60,
                    },
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        formula = serializer.save()

        self.assertEqual(formula.revision, 2)

    def test_update_draft_formula_replaces_and_edits_lines_in_place(self):
        formula = Formula.objects.create(
            name="Bread Formula",
            product=self.finished_product,
            revision=1,
            batch_size=100,
            yield_percentage=95,
            status="draft",
        )
        kept_line = FormulaLine.objects.create(
            formula=formula,
            sequence=1,
            line_type="MATERIAL",
            product=self.flour,
            quantity=60,
        )
        FormulaLine.objects.create(
            formula=formula,
            sequence=2,
            line_type="PROCESS",
            text="Old process",
        )

        serializer = FormulaWriteSerializer(
            formula,
            data={
                "name": "Bread Formula Rev 2",
                "product": str(self.finished_product.id),
                "batch_size": 120,
                "yield_percentage": 96,
                "status": "active",
                "is_active": True,
                "lines": [
                    {
                        "id": str(kept_line.id),
                        "sequence": 1,
                        "line_type": "MATERIAL",
                        "product": str(self.water.id),
                        "quantity": 40,
                    },
                    {
                        "sequence": 2,
                        "line_type": "INSTRUCTION",
                        "text": "Bake for 30 minutes.",
                    },
                ],
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_formula = serializer.save()

        self.assertEqual(updated_formula.id, formula.id)
        self.assertEqual(updated_formula.revision, 1)
        self.assertEqual(updated_formula.lines.count(), 2)
        self.assertFalse(
            updated_formula.lines.filter(text="Old process").exists()
        )

        kept_line.refresh_from_db()
        self.assertEqual(kept_line.product, self.water)
        self.assertEqual(kept_line.quantity, 40)
        self.assertEqual(updated_formula.status, "active")

    def test_update_formula_sets_deactivated_status_when_marked_inactive(self):
        formula = Formula.objects.create(
            name="Bread Formula",
            product=self.finished_product,
            revision=1,
            batch_size=100,
            yield_percentage=95,
            status="active",
            is_active=True,
        )
        FormulaLine.objects.create(
            formula=formula,
            sequence=1,
            line_type="MATERIAL",
            product=self.flour,
            quantity=60,
        )

        serializer = FormulaWriteSerializer(
            formula,
            data={
                "name": "Bread Formula",
                "product": str(self.finished_product.id),
                "batch_size": 100,
                "yield_percentage": 95,
                "is_active": False,
                "lines": [
                    {
                        "sequence": 1,
                        "line_type": "MATERIAL",
                        "product": str(self.flour.id),
                        "quantity": 60,
                    }
                ],
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_formula = serializer.save()

        self.assertFalse(updated_formula.is_active)
        self.assertEqual(updated_formula.status, "deactivated")

    def test_revise_active_formula_creates_draft_revision_without_mutating_source(self):
        formula = Formula.objects.create(
            name="Bread Formula",
            product=self.finished_product,
            revision=1,
            batch_size=100,
            yield_percentage=95,
            status="active",
            is_active=True,
        )
        material_line = FormulaLine.objects.create(
            formula=formula,
            sequence=1,
            line_type="MATERIAL",
            product=self.flour,
            quantity=60,
        )
        process_line = FormulaLine.objects.create(
            formula=formula,
            sequence=2,
            line_type="PROCESS",
            text="Old process",
        )

        serializer = FormulaWriteSerializer(
            formula,
            data={
                "name": "Bread Formula Rev 2",
                "batch_size": 120,
                "lines": [
                    {
                        "id": str(material_line.id),
                        "quantity": 40,
                    },
                    {
                        "sequence": 3,
                        "line_type": "INSTRUCTION",
                        "text": "Bake for 30 minutes.",
                    },
                ],
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        revised_formula = serializer.save()

        formula.refresh_from_db()
        material_line.refresh_from_db()
        process_line.refresh_from_db()

        self.assertNotEqual(revised_formula.id, formula.id)
        self.assertEqual(revised_formula.revision, 2)
        self.assertEqual(revised_formula.name, "Bread Formula Rev 2")
        self.assertEqual(revised_formula.batch_size, 120)
        self.assertEqual(revised_formula.status, "draft")
        self.assertFalse(revised_formula.is_active)

        self.assertEqual(formula.name, "Bread Formula")
        self.assertEqual(formula.batch_size, 100)
        self.assertEqual(formula.status, "active")
        self.assertEqual(material_line.quantity, 60)
        self.assertEqual(process_line.text, "Old process")

        self.assertEqual(revised_formula.lines.count(), 3)
        revised_material = revised_formula.lines.get(sequence=1)
        self.assertNotEqual(revised_material.id, material_line.id)
        self.assertEqual(revised_material.quantity, 40)
        self.assertTrue(revised_formula.lines.filter(text="Old process").exists())
        self.assertTrue(
            revised_formula.lines.filter(text="Bake for 30 minutes.").exists()
        )

    def test_revise_active_formula_full_line_payload_without_ids_does_not_duplicate_lines(self):
        formula = Formula.objects.create(
            name="Bread Formula",
            product=self.finished_product,
            revision=1,
            batch_size=100,
            yield_percentage=95,
            status="active",
            is_active=True,
        )
        FormulaLine.objects.create(
            formula=formula,
            sequence=1,
            line_type="MATERIAL",
            product=self.flour,
            quantity=60,
        )
        FormulaLine.objects.create(
            formula=formula,
            sequence=2,
            line_type="PROCESS",
            text="Old process",
        )

        serializer = FormulaWriteSerializer(
            formula,
            data={
                "batch_size": 120,
                "lines": [
                    {
                        "sequence": 1,
                        "line_type": "MATERIAL",
                        "product": str(self.flour.id),
                        "quantity": 60,
                    },
                    {
                        "sequence": 2,
                        "line_type": "PROCESS",
                        "text": "Old process",
                    },
                ],
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        revised_formula = serializer.save()

        self.assertEqual(revised_formula.lines.count(), 2)
        self.assertEqual(
            list(revised_formula.lines.order_by("sequence").values_list("sequence", flat=True)),
            [1, 2],
        )

    def test_formula_hold_and_archive_states(self):
        formula = Formula.objects.create(
            name="Bread Formula",
            product=self.finished_product,
            revision=1,
            batch_size=100,
            yield_percentage=95,
            status="active",
            is_active=True,
        )

        FormulaService.put_formula_on_hold(formula, "Quality review")
        formula.refresh_from_db()
        self.assertTrue(formula.on_hold)
        self.assertEqual(formula.on_hold_reason, "Quality review")

        with self.assertRaises(ValidationError):
            FormulaService.activate_formula(formula)

        FormulaService.release_formula_hold(formula)
        FormulaService.deactivate_formula(formula)
        FormulaService.archive_formula(formula)
        formula.refresh_from_db()

        self.assertEqual(formula.status, "archived")
        self.assertFalse(formula.is_active)
        self.assertFalse(formula.on_hold)
        self.assertEqual(formula.on_hold_reason, "")

    def test_activate_formula_deactivates_previous_active_revision(self):
        old_formula = Formula.objects.create(
            name="Bread Formula Rev 1",
            product=self.finished_product,
            revision=1,
            batch_size=100,
            yield_percentage=95,
            status="active",
            is_active=True,
        )
        new_formula = Formula.objects.create(
            name="Bread Formula Rev 2",
            product=self.finished_product,
            revision=2,
            batch_size=100,
            yield_percentage=95,
            status="draft",
            is_active=False,
        )

        FormulaService.activate_formula(new_formula)

        old_formula.refresh_from_db()
        new_formula.refresh_from_db()

        self.assertFalse(old_formula.is_active)
        self.assertEqual(old_formula.status, "deactivated")
        self.assertTrue(new_formula.is_active)
        self.assertEqual(new_formula.status, "active")

    def test_select_formula_skips_held_and_inactive_revisions(self):
        usable_formula = Formula.objects.create(
            name="Bread Formula Rev 1",
            product=self.finished_product,
            revision=1,
            batch_size=100,
            yield_percentage=95,
            status="active",
            is_active=True,
            on_hold=False,
        )
        Formula.objects.create(
            name="Bread Formula Rev 2",
            product=self.finished_product,
            revision=2,
            batch_size=100,
            yield_percentage=95,
            status="active",
            is_active=True,
            on_hold=True,
        )
        Formula.objects.create(
            name="Bread Formula Rev 3",
            product=self.finished_product,
            revision=3,
            batch_size=100,
            yield_percentage=95,
            status="active",
            is_active=False,
            on_hold=False,
        )

        class DummyOrder:
            formula_id = None

        order = DummyOrder()
        order.product = self.finished_product

        selected_formula = ProductionPlanner.select_formula(order)

        self.assertEqual(selected_formula.id, usable_formula.id)
