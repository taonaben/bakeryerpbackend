from rest_framework import serializers
from apps.accounting.models import ChartOfAccounts


class ChartOfAccountsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChartOfAccounts
        fields = [
            "id", "code", "name", "account_type", "account_subtype",
            "normal_balance", "system_key", "is_system_account",
            "is_active", "description", "created_at",
        ]
        read_only_fields = ["id", "system_key", "is_system_account", "created_at"]


class ChartOfAccountsCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChartOfAccounts
        fields = [
            "code", "name", "account_type", "account_subtype",
            "normal_balance", "description",
        ]


class ChartOfAccountsUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChartOfAccounts
        fields = ["name", "account_subtype", "description", "is_active", "code"]

    def validate(self, data):
        instance = self.instance
        if instance and instance.is_system_account and "code" in data:
            if data["code"] != instance.code:
                raise serializers.ValidationError(
                    {"code": "The code of a system account cannot be changed."}
                )
        return data
