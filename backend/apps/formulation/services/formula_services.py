from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from ..models import Formula, FormulaLine


FORMULA_UPDATABLE_FIELDS = (
    "name",
    "product",
    "batch_size",
    "yield_percentage",
    "is_active",
)


class FormulaService:
    @staticmethod
    def _resolve_status(formula, requested_status=None):
        if formula.status == "archived":
            return "archived"
        if formula.on_hold:
            return "on_hold"
        if not formula.is_active:
            return "deactivated"
        if requested_status in {"draft", "active"}:
            return requested_status
        if formula.status in {"draft", "active"}:
            return formula.status
        return "active"

    @staticmethod
    @transaction.atomic
    def create_with_lines(data):
        data = data.copy()
        lines_data = data.pop("lines", [])
        data.pop("revision", None)
        data["revision"] = FormulaService._next_revision(data["product"])
        data.setdefault("is_active", True)
        data["status"] = "draft" if data["is_active"] else "deactivated"
        formula = Formula.objects.create(**data)
        FormulaService._sync_lines(formula, lines_data)
        return formula

    @staticmethod
    @transaction.atomic
    def update_with_lines(formula, data, *, replace_lines=True):
        data = data.copy()
        lines_data = data.pop("lines", None)
        requested_status = data.pop("status", None)
        data.pop("revision", None)

        update_fields = []
        for field in FORMULA_UPDATABLE_FIELDS:
            if field in data:
                setattr(formula, field, data[field])
                update_fields.append(field)

        resolved_status = FormulaService._resolve_status(formula, requested_status)
        if formula.status != resolved_status:
            formula.status = resolved_status
            update_fields.append("status")

        if update_fields:
            formula.save(update_fields=update_fields)

        if lines_data is not None:
            FormulaService._sync_lines(
                formula,
                lines_data,
                replace_missing=replace_lines,
            )

        return formula

    @staticmethod
    @transaction.atomic
    def revise_with_lines(source_formula, data, *, replace_lines=True):
        source_formula = (
            Formula.objects.select_for_update()
            .select_related("product")
            .prefetch_related("lines")
            .get(id=source_formula.id)
        )

        data = data.copy()
        lines_data = data.pop("lines", None)
        data.pop("revision", None)
        data.pop("status", None)
        data.pop("is_active", None)

        product = data.get("product", source_formula.product)
        new_formula = Formula.objects.create(
            name=data.get("name", source_formula.name),
            product=product,
            revision=FormulaService._next_revision(product),
            batch_size=data.get("batch_size", source_formula.batch_size),
            yield_percentage=data.get(
                "yield_percentage",
                source_formula.yield_percentage,
            ),
            status="draft",
            is_active=False,
            on_hold=False,
            on_hold_reason="",
        )

        line_id_map, line_sequence_map = FormulaService._copy_lines(
            source_formula,
            new_formula,
        )

        if lines_data is not None:
            translated_lines = FormulaService._translate_revision_lines(
                lines_data,
                line_id_map,
                line_sequence_map,
            )
            FormulaService._sync_lines(
                new_formula,
                translated_lines,
                replace_missing=replace_lines,
            )

        return new_formula

    @staticmethod
    @transaction.atomic
    def activate_formula(formula):
        if formula.on_hold:
            raise ValidationError("Release the formula hold before activating it.")

        Formula.objects.filter(
            product=formula.product,
            status="active",
            is_active=True,
            on_hold=False,
        ).exclude(id=formula.id).update(is_active=False, status="deactivated")

        FormulaService._update_formula_state(
            formula,
            is_active=True,
            on_hold=False,
            on_hold_reason="",
            status="active",
        )

        return formula

    @staticmethod
    @transaction.atomic
    def deactivate_formula(formula):
        if not formula.is_active:
            raise ValidationError("Formula is already inactive.")

        FormulaService._update_formula_state(formula, is_active=False)
        return formula

    @staticmethod
    @transaction.atomic
    def archive_formula(formula):
        if (
            formula.status == "archived"
            and not formula.is_active
            and not formula.on_hold
            and not formula.on_hold_reason
        ):
            raise ValidationError("Formula is already archived.")

        FormulaService._update_formula_state(
            formula,
            is_active=False,
            on_hold=False,
            on_hold_reason="",
            status="archived",
        )
        return formula

    @staticmethod
    @transaction.atomic
    def put_formula_on_hold(formula, reason=""):
        if formula.on_hold:
            raise ValidationError("Formula is already on hold.")
        if not formula.is_active:
            raise ValidationError("Only active formulas can be put on hold.")
        if formula.status == "archived":
            raise ValidationError("Archived formulas cannot be put on hold.")

        FormulaService._update_formula_state(
            formula,
            on_hold=True,
            on_hold_reason=reason or "",
        )
        return formula

    @staticmethod
    @transaction.atomic
    def release_formula_hold(formula):
        if not formula.on_hold:
            raise ValidationError("Formula is not currently on hold.")

        FormulaService._update_formula_state(
            formula,
            on_hold=False,
            on_hold_reason="",
        )
        return formula

    @staticmethod
    def _update_formula_state(
        formula,
        *,
        is_active=None,
        on_hold=None,
        on_hold_reason=None,
        status=None,
    ):
        update_fields = []

        if is_active is not None and formula.is_active != is_active:
            formula.is_active = is_active
            update_fields.append("is_active")

        if on_hold is not None and formula.on_hold != on_hold:
            formula.on_hold = on_hold
            update_fields.append("on_hold")

        if on_hold_reason is not None and formula.on_hold_reason != on_hold_reason:
            formula.on_hold_reason = on_hold_reason
            update_fields.append("on_hold_reason")

        resolved_status = status or FormulaService._resolve_status(formula)
        if formula.status != resolved_status:
            formula.status = resolved_status
            update_fields.append("status")

        if update_fields:
            formula.save(update_fields=update_fields)

        return formula

    @staticmethod
    def _next_revision(product):
        latest_revision = (
            Formula.objects.filter(product=product).aggregate(Max("revision"))[
                "revision__max"
            ]
            or 0
        )
        return latest_revision + 1

    @staticmethod
    def _copy_lines(source_formula, target_formula):
        line_id_map = {}
        line_sequence_map = {}
        new_lines = []

        source_lines = list(source_formula.lines.order_by("sequence"))
        for source_line in source_lines:
            target_line = FormulaLine(
                formula=target_formula,
                sequence=source_line.sequence,
                line_type=source_line.line_type,
                product=source_line.product,
                quantity=source_line.quantity,
                text=source_line.text,
            )
            new_lines.append(target_line)
            line_id_map[str(source_line.id)] = target_line
            line_sequence_map[source_line.sequence] = target_line

        if new_lines:
            FormulaLine.objects.bulk_create(new_lines)

        return (
            {source_id: str(line.id) for source_id, line in line_id_map.items()},
            {
                sequence: str(line.id)
                for sequence, line in line_sequence_map.items()
            },
        )

    @staticmethod
    def _translate_revision_lines(lines_data, line_id_map, line_sequence_map):
        translated_lines = []

        for line_data in lines_data:
            line_data = line_data.copy()
            line_id = str(line_data.get("id")) if line_data.get("id") else None
            if line_id:
                new_line_id = line_id_map.get(line_id)
                if not new_line_id:
                    raise ValidationError(
                        {
                            "lines": [
                                f"Line '{line_id}' does not belong to this formula."
                            ]
                        }
                    )
                line_data["id"] = new_line_id
            elif line_data.get("sequence") in line_sequence_map:
                line_data["id"] = line_sequence_map[line_data["sequence"]]

            translated_lines.append(line_data)

        return translated_lines

    @staticmethod
    def _sync_lines(formula, lines_data, *, replace_missing=True):
        existing_lines = {str(line.id): line for line in formula.lines.all()}
        kept_line_ids = set()
        new_lines = []
        updated_lines = []

        for line_data in lines_data:
            line_id = str(line_data.get("id")) if line_data.get("id") else None

            if line_id:
                line = existing_lines.get(line_id)
                if not line:
                    raise ValidationError(
                        {
                            "lines": [
                                f"Line '{line_id}' does not belong to this formula."
                            ]
                        }
                    )

                for field in ("sequence", "line_type", "product", "quantity", "text"):
                    if field in line_data:
                        setattr(line, field, line_data[field])
                updated_lines.append(line)
                kept_line_ids.add(line_id)
                continue

            new_lines.append(
                FormulaLine(
                    formula=formula,
                    sequence=line_data["sequence"],
                    line_type=line_data["line_type"],
                    product=line_data.get("product"),
                    quantity=line_data.get("quantity"),
                    text=line_data.get("text"),
                )
            )

        if updated_lines:
            FormulaLine.objects.bulk_update(
                updated_lines,
                ["sequence", "line_type", "product", "quantity", "text"],
            )

        if new_lines:
            FormulaLine.objects.bulk_create(new_lines)

        if replace_missing:
            stale_line_ids = [
                line.id
                for key, line in existing_lines.items()
                if key not in kept_line_ids
            ]
            if stale_line_ids:
                FormulaLine.objects.filter(id__in=stale_line_ids).delete()
