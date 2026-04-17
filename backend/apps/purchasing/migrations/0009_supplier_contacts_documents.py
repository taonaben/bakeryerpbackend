import uuid
import django.db.models.deletion
import apps.purchasing.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchasing", "0008_supplier_extended_fields"),
        ("central", "0007_product_shelf_life_days_product_storage_conditions_and_more"),
    ]

    operations = [
        # warehouses_served M2M on Supplier
        migrations.AddField(
            model_name="supplier",
            name="warehouses_served",
            field=models.ManyToManyField(
                blank=True,
                related_name="served_suppliers",
                to="central.warehouse",
            ),
        ),
        # SupplierContact
        migrations.CreateModel(
            name="SupplierContact",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        primary_key=True,
                        default=uuid.uuid4,
                        editable=False,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("role", models.CharField(max_length=100, blank=True)),
                ("email", models.EmailField(blank=True)),
                ("phone", models.CharField(max_length=20, blank=True)),
                ("is_primary", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contacts",
                        to="purchasing.supplier",
                    ),
                ),
            ],
        ),
        # SupplierDocument
        migrations.CreateModel(
            name="SupplierDocument",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        primary_key=True,
                        default=uuid.uuid4,
                        editable=False,
                        serialize=False,
                    ),
                ),
                (
                    "document_type",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("CONTRACT", "Contract"),
                            ("HEALTH_CERT", "Health Certificate"),
                            ("TAX_CLEARANCE", "Tax Clearance"),
                            ("CERTIFICATION", "Certification"),
                            ("OTHER", "Other"),
                        ],
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("file_url", models.CharField(max_length=500, blank=True)),
                ("file_name", models.CharField(max_length=255, blank=True)),
                ("issued_date", models.DateField(null=True, blank=True)),
                ("expiry_date", models.DateField(null=True, blank=True)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="purchasing.supplier",
                    ),
                ),
            ],
        ),
    ]
