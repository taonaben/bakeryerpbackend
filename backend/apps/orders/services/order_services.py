from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.production.serializers import (
    ProductionOrderSerializer,
    ProductionPlanSerializer,
)
from apps.production.services.production_planner import ProductionPlanner


def get_queue_queryset(queryset, warehouse_id=None):
    if warehouse_id:
        queryset = queryset.filter(warehouse_id=warehouse_id)

    return (
        queryset.filter(status="planned")
        .annotate(
            override_approved=Case(
                When(
                    priority_override_approved_at__isnull=False,
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by(
            "-override_approved",
            "priority_override_approved_at",
            "need_by",
            "created_at",
        )
    )


def get_queue_positions(queue_queryset):
    ordered_ids = list(queue_queryset.values_list("id", flat=True))
    return {str(order_id): index + 1 for index, order_id in enumerate(ordered_ids)}


def build_priority_approval_payload(planned_order, positions):
    if planned_order.priority != "high":
        return {
            "can_request": False,
            "reason": "Only high priority orders can request queue override.",
        }

    position = positions.get(str(planned_order.id))
    jobs_ahead = max(position - 1, 0) if position else 0

    return {
        "can_request": True,
        "jobs_ahead": jobs_ahead,
        "approved": planned_order.priority_override_approved_at is not None,
    }


def approve_priority_override(planned_order, user, approve, note=None):
    if planned_order.priority != "high":
        raise DjangoValidationError(
            "Only high priority orders can request queue override."
        )

    if not approve:
        raise DjangoValidationError("Approval confirmation is required.")

    if planned_order.priority_override_approved_at:
        raise DjangoValidationError("Priority override has already been approved.")

    planned_order.priority_override_requested_at = (
        planned_order.priority_override_requested_at or timezone.now()
    )
    planned_order.priority_override_approved_at = timezone.now()
    planned_order.priority_override_approved_by = user
    if note is not None:
        planned_order.priority_override_note = note

    planned_order.save(
        update_fields=[
            "priority_override_requested_at",
            "priority_override_approved_at",
            "priority_override_approved_by",
            "priority_override_note",
        ]
    )

    return planned_order


def create_production_order_from_planned(planned_order, scheduled_start, scheduled_end):
    if planned_order.status in ["cancelled", "completed"]:
        raise DjangoValidationError(
            "Planned order cannot be converted in its current state."
        )

    if not scheduled_start or not scheduled_end:
        raise DjangoValidationError(
            "scheduled_start and scheduled_end are required to create a production order."
        )

    formula = ProductionPlanner.select_formula(planned_order)

    payload = {
        "product": planned_order.product_id,
        "quantity": planned_order.quantity,
        "warehouse": planned_order.warehouse_id,
        "formula": formula.id,
        "scheduled_start": scheduled_start,
        "scheduled_end": scheduled_end,
        "planned_order": planned_order.id,
    }

    serializer = ProductionOrderSerializer(data=payload)
    try:
        serializer.is_valid(raise_exception=True)
    except DRFValidationError as exc:
        raise DjangoValidationError(exc.detail)

    serializer.save()

    if planned_order.status == "draft":
        planned_order.status = "planned"
        planned_order.save(update_fields=["status"])

    return serializer


def create_production_order_and_plan(planned_order, scheduled_start, scheduled_end):
    serializer = create_production_order_from_planned(
        planned_order, scheduled_start, scheduled_end
    )
    production_order = serializer.instance
    plan = ProductionPlanner.plan(production_order)
    plan_data = ProductionPlanSerializer(plan).data
    return serializer, plan_data
