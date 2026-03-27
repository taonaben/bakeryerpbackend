from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.production.models import ProductionOrder

from central.models import Company, Product, Warehouse
from apps.formulation.models import Formula

from .models import PlannedOrder
from .services.order_services import (
    approve_priority_override,
    build_priority_approval_payload,
    create_production_order_from_planned,
    get_queue_positions,
    get_queue_queryset,
)


class PlannedOrderServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Bakery Co")
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            name="Main Production",
            wh_type="production",
        )
        self.product = Product.objects.create(
            name="Sourdough",
            company=self.company,
            category="Bread",
            unit_of_measure="kg",
        )
        self.formula = Formula.objects.create(
            name="Sourdough Formula",
            product=self.product,
            revision=1,
            batch_size=10,
            yield_percentage=95,
            status="active",
        )
        self.user = get_user_model().objects.create_user(
            username="manager",
            email="manager@example.com",
            role="manager",
            password="password123",
        )

    def _create_planned_order(self, **kwargs):
        defaults = {
            "product": self.product,
            "quantity": Decimal("10"),
            "warehouse": self.warehouse,
            "need_by": timezone.now() + timezone.timedelta(days=1),
            "priority": "normal",
            "status": "planned",
        }
        defaults.update(kwargs)
        return PlannedOrder.objects.create(**defaults)

    def test_queue_positions_prioritize_approved_override(self):
        first = self._create_planned_order(
            need_by=timezone.now() + timezone.timedelta(days=2)
        )
        second = self._create_planned_order(
            need_by=timezone.now() + timezone.timedelta(days=1),
            priority="high",
            priority_override_approved_at=timezone.now(),
        )

        queue = get_queue_queryset(PlannedOrder.objects.all())
        positions = get_queue_positions(queue)

        self.assertEqual(positions[str(second.id)], 1)
        self.assertEqual(positions[str(first.id)], 2)

    def test_build_priority_approval_payload(self):
        planned_order = self._create_planned_order(priority="high")
        positions = {str(planned_order.id): 3}

        payload = build_priority_approval_payload(planned_order, positions)

        self.assertTrue(payload["can_request"])
        self.assertEqual(payload["jobs_ahead"], 2)
        self.assertFalse(payload["approved"])

    def test_approve_priority_override_sets_fields(self):
        planned_order = self._create_planned_order(priority="high")

        approve_priority_override(
            planned_order, user=self.user, approve=True, note="Urgent customer"
        )
        planned_order.refresh_from_db()

        self.assertIsNotNone(planned_order.priority_override_requested_at)
        self.assertIsNotNone(planned_order.priority_override_approved_at)
        self.assertEqual(planned_order.priority_override_approved_by, self.user)
        self.assertEqual(planned_order.priority_override_note, "Urgent customer")

    def test_create_production_order_from_planned(self):
        planned_order = self._create_planned_order(status="draft")

        scheduled_start = timezone.now()
        scheduled_end = scheduled_start + timezone.timedelta(hours=4)

        serializer = create_production_order_from_planned(
            planned_order, scheduled_start, scheduled_end
        )

        planned_order.refresh_from_db()
        self.assertEqual(planned_order.status, "planned")

        production_order = ProductionOrder.objects.get(id=serializer.data["id"])
        self.assertEqual(production_order.product_id, self.product.id)
        self.assertEqual(production_order.planned_order_id, planned_order.id)
