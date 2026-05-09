from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("formulation", "0005_alter_formula_status"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="formula",
            constraint=models.UniqueConstraint(
                fields=("product", "revision"),
                name="unique_formula_product_revision",
            ),
        ),
    ]
