from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("formulation", "0006_formula_unique_product_revision"),
    ]

    operations = [
        migrations.AddField(
            model_name="formula",
            name="labor_minutes_per_batch",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                max_digits=14,
                null=True,
            ),
        ),
    ]
