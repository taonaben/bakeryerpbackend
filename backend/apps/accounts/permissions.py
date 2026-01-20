from rest_framework.permissions import BasePermission

PERMISSION_MATRIX = {
    "warehouse_staff": {
        "inventory": "full",
    },
    "production_operator": {
        "inventory": "read",
        "production": "full",
    },
    "production_supervisor": {
        "inventory": "read",
        "production": "full",
        "quality": "read",
    },
    "inventory_controller": {
        "inventory": "full",
        "production": "read",
        "quality": "read",
    },
    "planner": {
        "inventory": "read",
        "production": "read",
        "sales": "read",
        "purchasing": "read",
    },
    "sales_rep": {
        "inventory": "read",
        "sales": "full",
    },
    "purchasing_officer": {
        "inventory": "read",
        "purchasing": "full",
    },
    "accountant": {
        "inventory": "read",
        "sales": "read",
        "purchasing": "read",
        "finance": "full",
    },
    "quality_officer": {
        "inventory": "read",
        "production": "read",
        "quality": "full",
    },
    "manager": {
        "inventory": "read",
        "production": "read",
        "sales": "read",
        "purchasing": "read",
        "finance": "read",
        "quality": "read",
        "users": "read",
    },
    "owner_director": {
        "inventory": "full",
        "production": "full",
        "sales": "full",
        "purchasing": "full",
        "finance": "full",
        "quality": "full",
        "users": "full",
    },
    "system_admin": {
        "users": "full",
    },
}


# Class based permission for DRF views
class ModulePermission(BasePermission):
    module = None

    def has_permission(self, request, view):
        if not request.user.is_authenticated or not hasattr(request.user, "role"):
            return False

        action = "read" if request.method in ["GET", "HEAD", "OPTIONS"] else "full"
        user_perms = PERMISSION_MATRIX.get(request.user.role, {})
        module_perm = user_perms.get(self.module)

        if module_perm == "full":
            return True
        elif module_perm == "read" and action == "read":
            return True

        return False
