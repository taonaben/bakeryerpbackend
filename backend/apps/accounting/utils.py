import re
from django.db import transaction


def generate_entry_number(company) -> str:
    """
    Generate a sequential, zero-padded 5-digit journal entry number.
    Format: JNL-00001
    Uses select_for_update to prevent duplicates under concurrent access.
    """
    from apps.accounting.models import JournalEntry

    with transaction.atomic():
        existing = (
            JournalEntry.objects.select_for_update()
            .filter(company=company, entry_number__startswith="JNL-")
            .values_list("entry_number", flat=True)
        )
        pattern = re.compile(r"^JNL-(\d+)$")
        max_num = 0
        for val in existing:
            m = pattern.match(val)
            if m:
                n = int(m.group(1))
                if n > max_num:
                    max_num = n
        return f"JNL-{max_num + 1:05d}"
