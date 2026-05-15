from django.db import migrations, models


def renumber_duplicate_formula_revisions(apps, schema_editor):
    Formula = apps.get_model("formulation", "Formula")

    product_ids = (
        Formula.objects.order_by()
        .values_list("product_id", flat=True)
        .distinct()
    )

    for product_id in product_ids:
        formulas = list(
            Formula.objects.filter(product_id=product_id).order_by(
                "revision",
                "created_at",
                "id",
            )
        )
        if not formulas:
            continue

        used_revisions = set()
        next_revision = max(formula.revision for formula in formulas) + 1

        for formula in formulas:
            if formula.revision not in used_revisions:
                used_revisions.add(formula.revision)
                continue

            while next_revision in used_revisions:
                next_revision += 1

            formula.revision = next_revision
            formula.save(update_fields=["revision"])
            used_revisions.add(next_revision)
            next_revision += 1


class Migration(migrations.Migration):

    dependencies = [
        ("formulation", "0005_alter_formula_status"),
    ]

    operations = [
        migrations.RunPython(
            renumber_duplicate_formula_revisions,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="formula",
            constraint=models.UniqueConstraint(
                fields=("product", "revision"),
                name="unique_formula_product_revision",
            ),
        ),
    ]
