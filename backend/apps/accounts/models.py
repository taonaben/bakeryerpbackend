from django.db import models
from django.contrib.auth.models import AbstractUser
from central.models import Company
import uuid
import string
import random
import time


def generate_employee_code():
    """Generate a simple employee code without database checks"""
    chars = string.ascii_uppercase + string.digits
    return (
        "".join(random.choices(chars, k=3)) + "-" + "".join(random.choices(chars, k=3))
    )


class User(AbstractUser):
    """User's core fields, that will be used everywhere, Uses the employee code as unique identifier"""

    ROLE_CHOICES = [
        ("warehouse_staff", "Warehouse Staff"),
        ("production_operator", "Production Operator"),
        ("production_supervisor", "Production Supervisor"),
        ("inventory_controller", "Inventory Controller"),
        ("planner", "Planner"),
        ("sales_rep", "Sales Rep"),
        ("purchasing_officer", "Purchasing Officer"),
        ("accountant", "Accountant"),
        ("quality_officer", "Quality Officer"),
        ("manager", "Manager"),
        ("owner_director", "Owner / Director"),
        ("system_admin", "System Admin"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emp_code = models.CharField(
        max_length=7, unique=True, default=generate_employee_code
    )
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        null=False,
        blank=False,
    )
    company = models.ForeignKey(
        Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )

    groups = models.ManyToManyField(
        "auth.Group",
        related_name="bakery_user_set",
        blank=True,
        help_text="The groups this user belongs to.",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="bakery_user_set",
        blank=True,
        help_text="Specific permissions for this user.",
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["role"], name="user_role_idx"),
            models.Index(fields=["emp_code"], name="user_emp_code_idx"),
        ]

    def __str__(self):
        return self.username
