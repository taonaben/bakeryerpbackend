import django_filters
from django.contrib.auth import get_user_model


User = get_user_model()


class UserFilter(django_filters.FilterSet):
    """FilterSet for account users."""

    class Meta:
        model = User
        fields = {
            "emp_code": ["exact", "icontains"],
            "email": ["exact", "icontains"],
            "first_name": ["exact", "icontains"],
            "last_name": ["exact", "icontains"],
            "username": ["exact", "icontains"],
            "role": ["exact"],
            "is_active": ["exact"],
            "is_staff": ["exact"],
            "date_joined": ["exact", "gt", "lt", "gte", "lte"],
        }
