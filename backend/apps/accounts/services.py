from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied, ValidationError

from .permissions import PERMISSION_MATRIX


User = get_user_model()


SELF_EDITABLE_FIELDS = {"username"}


def get_company_user_queryset(actor):
    """
    Return users visible to actor.

    Accounts are company scoped: even staff users only work inside the company
    linked to their account.
    """
    company_id = getattr(actor, "company_id", None)
    if not company_id:
        raise PermissionDenied("Your account is not linked to a company.")

    return User.objects.select_related("company").filter(company_id=company_id)


def is_self_edit(actor, target_user):
    return getattr(actor, "id", None) == getattr(target_user, "id", None)


def has_user_management_permission(actor):
    if not getattr(actor, "is_authenticated", False):
        return False
    if getattr(actor, "is_superuser", False) or getattr(actor, "is_staff", False):
        return True

    module_perm = PERMISSION_MATRIX.get(getattr(actor, "role", None), {}).get("users")
    return module_perm == "full"


def ensure_can_manage_users(actor):
    if not has_user_management_permission(actor):
        raise PermissionDenied("You do not have permission to manage users.")


def validate_user_update(actor, target_user, validated_data):
    """
    Users may edit only their own username.
    Managing other users requires full users permission.
    """
    if is_self_edit(actor, target_user):
        blocked_fields = set(validated_data) - SELF_EDITABLE_FIELDS
        if blocked_fields:
            raise PermissionDenied(
                "You can only update your own username from this endpoint."
            )
        return

    ensure_can_manage_users(actor)


def update_user(actor, target_user, validated_data):
    validate_user_update(actor, target_user, validated_data)

    if not validated_data:
        return target_user

    for field, value in validated_data.items():
        setattr(target_user, field, value)
    target_user.save(update_fields=list(validated_data.keys()))
    return target_user


def delete_user(actor, target_user):
    if is_self_edit(actor, target_user):
        raise PermissionDenied("You cannot delete your own account.")
    ensure_can_manage_users(actor)
    target_user.delete()


def change_own_password(actor, old_password, new_password):
    if not actor.check_password(old_password):
        raise ValidationError({"old_password": "Old password is incorrect."})

    actor.set_password(new_password)
    actor.save(update_fields=["password"])
    return actor


def override_user_password(actor, target_user, new_password):
    if is_self_edit(actor, target_user):
        raise ValidationError(
            {
                "detail": (
                    "Use the self password change endpoint when changing your "
                    "own password."
                )
            }
        )

    ensure_can_manage_users(actor)
    target_user.set_password(new_password)
    target_user.save(update_fields=["password"])
    return target_user
