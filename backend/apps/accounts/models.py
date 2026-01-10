from django.db import models
from django.contrib.auth.models import AbstractUser
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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emp_code = models.CharField(
        max_length=7, unique=True, default=generate_employee_code
    )
    email = models.EmailField(unique=True)
    department = models.CharField(
        choices=[
            ("HR", "Human Resources"),
            ("ENG", "Engineering"),
            ("MKT", "Marketing"),
        ],
        max_length=3,
        null=True,
        blank=True,
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

    def __str__(self):
        return self.username
