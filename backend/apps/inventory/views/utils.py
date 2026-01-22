from apps.accounts.permissions import ModulePermission
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class InventoryPermission(ModulePermission):
    module = "inventory"


filter_backends = [
    DjangoFilterBackend,
    filters.OrderingFilter,
    filters.SearchFilter,
]
