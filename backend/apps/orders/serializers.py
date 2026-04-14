from rest_framework import serializers

from apps.production.serializers import (
    ProductionOrderSerializer,
    ProductionPlanSerializer,
)
from apps.production.services.production_planner import ProductionPlanner

from .models import PlannedOrder


class PlannedOrderSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    production_order_id = serializers.UUIDField(
        source="production_order.id", read_only=True
    )
    production_order_status = serializers.CharField(
        source="production_order.status", read_only=True
    )
    planning = serializers.SerializerMethodField()
    queue_position = serializers.SerializerMethodField()
    can_request_priority_override = serializers.SerializerMethodField()

    class Meta:
        model = PlannedOrder
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "warehouse",
            "warehouse_name",
            "need_by",
            "priority",
            "status",
            "priority_override_requested_at",
            "priority_override_approved_at",
            "priority_override_approved_by",
            "priority_override_note",
            "created_at",
            "updated_at",
            "production_order_id",
            "production_order_status",
            "planning",
            "queue_position",
            "can_request_priority_override",
        ]
        read_only_fields = [
            "priority_override_requested_at",
            "priority_override_approved_at",
            "priority_override_approved_by",
            "created_at",
            "updated_at",
            "production_order_id",
            "production_order_status",
            "planning",
            "queue_position",
            "can_request_priority_override",
        ]

    def get_planning(self, obj):
        plan = ProductionPlanner.plan_for_planned_order(obj)
        return ProductionPlanSerializer(plan).data

    def get_queue_position(self, obj):
        positions = self.context.get("queue_positions", {})
        return positions.get(str(obj.id))

    def get_can_request_priority_override(self, obj):
        return obj.priority == "high" and obj.priority_override_approved_at is None


class PlannedOrderProductionCreateSerializer(serializers.Serializer):
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()


class PlannedOrderPriorityApproveSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PlannedOrderPriorityApprovalSerializer(serializers.Serializer):
    can_request = serializers.BooleanField(read_only=True)
    reason = serializers.CharField(read_only=True, required=False)
    jobs_ahead = serializers.IntegerField(read_only=True, required=False)
    approved = serializers.BooleanField(read_only=True, required=False)


class PlannedOrderPriorityApproveResponseSerializer(serializers.Serializer):
    message = serializers.CharField(read_only=True)
    queue_position = serializers.IntegerField(read_only=True, allow_null=True)


class PlannedOrderProductionPlanResponseSerializer(serializers.Serializer):
    production_order = ProductionOrderSerializer(read_only=True)
    plan = ProductionPlanSerializer(read_only=True)
