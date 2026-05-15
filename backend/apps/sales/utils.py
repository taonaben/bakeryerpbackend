import re

from django.db import transaction


def generate_reference_number(prefix: str, model_class, field: str) -> str:
    """
    Generate a sequential, zero-padded 5-digit reference number for a given model.

    Uses SELECT MAX with select_for_update() inside a transaction to ensure
    no duplicate numbers are produced under concurrent access.

    Examples:
        generate_reference_number("SO", SalesOrder, "order_number")  -> "SO-00001"
        generate_reference_number("DEL", Delivery, "delivery_number") -> "DEL-00001"
        generate_reference_number("INV", Invoice, "invoice_number")   -> "INV-00001"
    """
    with transaction.atomic():
        # Lock the table by selecting the max value with select_for_update
        existing = (
            model_class.objects
            .select_for_update()
            .filter(**{f"{field}__startswith": f"{prefix}-"})
            .values_list(field, flat=True)
        )

        max_number = 0
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
        for value in existing:
            match = pattern.match(value)
            if match:
                num = int(match.group(1))
                if num > max_number:
                    max_number = num

        next_number = max_number + 1
        return f"{prefix}-{next_number:05d}"
