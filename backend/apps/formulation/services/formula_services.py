from django.db import transaction
from ..models import Formula, FormulaLine


class FormulaService:

    @staticmethod
    @transaction.atomic
    def create_with_lines(data):
        # Create formula
        data = data.copy()
        lines_data = data.pop("lines", [])
        data.setdefault("status", "draft")
        formula = Formula.objects.create(**data)

        # Build objects in memory
        lines = [
            FormulaLine(
                formula=formula,
                sequence=line["sequence"],
                line_type=line["line_type"],
                product=line.get("product"),
                quantity=line.get("quantity"),
                text=line.get("text"),
            )
            for line in lines_data
        ]

        # Bulk insert
        FormulaLine.objects.bulk_create(lines)

        return formula
