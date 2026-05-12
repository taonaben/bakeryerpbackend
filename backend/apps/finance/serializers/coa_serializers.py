from rest_framework import serializers
from apps.accounting.models import ChartOfAccounts


class ChartOfAccountsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChartOfAccounts
        fields = [
            "id",
            "code",
            "name",
            "account_type",
            "account_subtype",
            "normal_balance",
            "system_key",
            "is_system_account",
            "is_active",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "system_key", "is_system_account", "created_at"]


class ChartOfAccountsCreateSerializer(serializers.ModelSerializer):
    code = serializers.CharField(help_text="Unique account code within the company.")
    name = serializers.CharField(help_text="Ledger account display name.")
    account_type = serializers.ChoiceField(
        choices=ChartOfAccounts.ACCOUNT_TYPE_CHOICES,
        help_text="Top-level account type (asset, liability, equity, revenue, expense).",
    )
    account_subtype = serializers.ChoiceField(
        choices=ChartOfAccounts.ACCOUNT_SUBTYPE_CHOICES,
        required=False,
        allow_blank=True,
        help_text="Optional subtype used for reporting buckets.",
    )
    normal_balance = serializers.ChoiceField(
        choices=ChartOfAccounts.NORMAL_BALANCE_CHOICES,
        help_text="Expected natural balance direction for this account.",
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional account description for finance users.",
    )

    class Meta:
        model = ChartOfAccounts
        fields = [
            "code",
            "name",
            "account_type",
            "account_subtype",
            "normal_balance",
            "description",
        ]


class ChartOfAccountsUpdateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        required=False,
        help_text="Updated ledger account name.",
    )
    account_subtype = serializers.ChoiceField(
        choices=ChartOfAccounts.ACCOUNT_SUBTYPE_CHOICES,
        required=False,
        allow_blank=True,
        help_text="Updated reporting subtype.",
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Updated account description.",
    )
    is_active = serializers.BooleanField(
        required=False,
        help_text="Set false to deactivate a non-system account.",
    )
    code = serializers.CharField(
        required=False,
        help_text="Updated code (blocked for system accounts).",
    )

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
