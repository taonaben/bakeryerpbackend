from rest_framework.exceptions import PermissionDenied


class CompanyScopedMixin:
    """
    Mixin that auto-filters querysets by the logged-in user's company.

    Subclasses must set ``company_field`` to the ORM lookup path from the
    viewset's model to the Company FK.  Examples::

        company_field = "company"               # Supplier, Warehouse, Product
        company_field = "warehouse__company"     # PurchaseOrder, GoodsReceipt
        company_field = "product__company"       # Formula
        company_field = "purchase_order__warehouse__company"  # PO line items

    A ``?company_id`` query-param override is accepted but only from staff
    users; regular users are always locked to their own company.
    """

    company_field = None  # MUST be set by subclass

    def get_company_filter(self):
        user = self.request.user
        company_id = getattr(user, "company_id", None)

        override = self.request.query_params.get("company_id")
        if override and getattr(user, "is_staff", False):
            company_id = override

        if not company_id:
            raise PermissionDenied("Your account is not linked to a company.")

        return {self.company_field: company_id}

    def get_queryset(self):
        qs = super().get_queryset()
        if self.company_field:
            qs = qs.filter(**self.get_company_filter())
        return qs
