from rest_framework import serializers
from .models import DashboardWidget
from .widgets import WIDGET_REGISTRY


class DashboardWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = ["widget_key", "position", "is_visible", "width"]


class WidgetItemSerializer(serializers.Serializer):
    widget_key = serializers.CharField(max_length=100)
    position = serializers.IntegerField(min_value=0)
    is_visible = serializers.BooleanField(default=True)
    width = serializers.ChoiceField(choices=["half", "full"], default="half")


class LayoutSaveSerializer(serializers.Serializer):
    layout = WidgetItemSerializer(many=True)

    def validate_layout(self, value):
        valid_keys = set(WIDGET_REGISTRY.keys())
        for item in value:
            if item["widget_key"] not in valid_keys:
                raise serializers.ValidationError(
                    f"Unknown widget_key: '{item['widget_key']}'"
                )
        positions = [item["position"] for item in value]
        if len(positions) != len(set(positions)):
            raise serializers.ValidationError("Duplicate positions are not allowed.")
        return value
