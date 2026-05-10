from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("costing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="overheadrate",
            name="planned_labor_minutes",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text=(
                    "Total planned facility labor driver capacity for this warehouse "
                    "and period, not per-product labor usage."
                ),
                max_digits=14,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="overheadrate",
            name="rate_per_labor_minute",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=14,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="standardcost",
            name="overhead_allocation_method",
            field=models.CharField(
                choices=[
                    ("labor_minutes", "Labor Minutes"),
                    ("unit_rate", "Unit Rate"),
                ],
                default="unit_rate",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="costingentry",
            name="overhead_allocation_method",
            field=models.CharField(
                choices=[
                    ("labor_minutes", "Labor Minutes"),
                    ("unit_rate", "Unit Rate"),
                ],
                default="unit_rate",
                max_length=30,
            ),
        ),
    ]
