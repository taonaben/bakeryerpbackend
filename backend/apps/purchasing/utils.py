from django.utils import timezone


def generate_company_year_number(
    *,
    model_cls,
    prefix,
    company,
    number_field,
    company_field="company",
    date_field="created_at",
    width=4,
):
    """Generate a document number like PR-2026-0001 scoped by company and year."""

    year = timezone.now().year
    filters = {
        company_field: company,
        f"{date_field}__year": year,
    }

    last_doc = (
        model_cls.objects.filter(**filters).order_by(date_field, number_field).last()
    )

    if not last_doc:
        next_seq = 1
    else:
        raw_number = str(getattr(last_doc, number_field, ""))
        parts = raw_number.split("-")
        if (
            len(parts) >= 3
            and parts[0] == prefix
            and parts[1].isdigit()
            and int(parts[1]) == year
            and parts[-1].isdigit()
        ):
            next_seq = int(parts[-1]) + 1
        else:
            next_seq = 1

    return f"{prefix}-{year}-{next_seq:0{width}d}"
