import django.core.validators
from django.db import migrations, models
import apps.purchasing.models


class Migration(migrations.Migration):

    dependencies = [
        ("purchasing", "0007_supplier_company"),
        ("central", "0007_product_shelf_life_days_product_storage_conditions_and_more"),
    ]

    operations = [
        # Rename email → primary_email
        migrations.RenameField(
            model_name="supplier",
            old_name="email",
            new_name="primary_email",
        ),
        # Rename phone_number → primary_phone
        migrations.RenameField(
            model_name="supplier",
            old_name="phone_number",
            new_name="primary_phone",
        ),
        # Alter address to allow blank
        migrations.AlterField(
            model_name="supplier",
            name="address",
            field=models.TextField(blank=True),
        ),
        # Alter payment_terms to choices field
        migrations.AlterField(
            model_name="supplier",
            name="payment_terms",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("NET_30", "Net 30"),
                    ("NET_60", "Net 60"),
                    ("COD", "Cash on Delivery"),
                    ("EOM", "End of Month"),
                    ("PREPAID", "Prepaid"),
                    ("IMMEDIATE", "Immediate"),
                ],
                blank=True,
            ),
        ),
        # Identity & Compliance
        migrations.AddField(
            model_name="supplier",
            name="registration_number",
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="tax_number",
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="supplier_type",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("MANUFACTURER", "Manufacturer"),
                    ("DISTRIBUTOR", "Distributor"),
                    ("AGENT", "Agent"),
                    ("INDIVIDUAL", "Individual"),
                ],
                blank=True,
            ),
        ),
        # Contact & Location
        migrations.AddField(
            model_name="supplier",
            name="secondary_email",
            field=models.EmailField(blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="alternate_phone",
            field=models.CharField(max_length=20, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="country",
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="city",
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="website",
            field=models.URLField(blank=True),
        ),
        # Financial
        migrations.AddField(
            model_name="supplier",
            name="credit_limit",
            field=models.DecimalField(
                max_digits=12, decimal_places=2, null=True, blank=True
            ),
        ),
        migrations.AddField(
            model_name="supplier",
            name="bank_name",
            field=models.CharField(max_length=200, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="bank_branch",
            field=models.CharField(max_length=200, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="bank_account_number",
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="can_supply_on_credit",
            field=models.BooleanField(default=False),
        ),
        # Logistics
        migrations.AddField(
            model_name="supplier",
            name="default_lead_time_days",
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="minimum_order_value",
            field=models.DecimalField(
                max_digits=12, decimal_places=2, null=True, blank=True
            ),
        ),
        migrations.AddField(
            model_name="supplier",
            name="delivery_days",
            field=models.JSONField(
                default=list,
                blank=True,
                validators=[apps.purchasing.models.validate_delivery_days],
            ),
        ),
        migrations.AddField(
            model_name="supplier",
            name="delivery_method",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("OWN_TRANSPORT", "Own Transport"),
                    ("COURIER", "Courier"),
                    ("COLLECT", "Collect"),
                ],
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="supplier",
            name="delivery_radius_km",
            field=models.DecimalField(
                max_digits=8, decimal_places=2, null=True, blank=True
            ),
        ),
        # Performance & Internal
        migrations.AddField(
            model_name="supplier",
            name="rating",
            field=models.IntegerField(
                null=True,
                blank=True,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5),
                ],
            ),
        ),
        migrations.AddField(
            model_name="supplier",
            name="internal_notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="supplier",
            name="on_hold",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="supplier",
            name="on_hold_reason",
            field=models.TextField(blank=True),
        ),
    ]
