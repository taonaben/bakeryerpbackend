"""
COGS posting is triggered internally by the sales module signal.
This view exposes a manual trigger for testing and re-posting scenarios.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.costing.services.cogs_posting import COGSPostingService, COGSPostingError


class COGSPostView(APIView):
    """
    POST /costing/cogs/post
    Body: { "sales_order_id": "<uuid>" }

    Manually triggers COGS posting for a sales order.
    Normally fired automatically by the sales order confirmation signal.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sales_order_id = request.data.get("sales_order_id")
        if not sales_order_id:
            return Response(
                {"detail": "sales_order_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from apps.sales.models import SalesOrder  # lazy import — sales module optional
            order = SalesOrder.objects.get(pk=sales_order_id)
        except ImportError:
            return Response(
                {"detail": "Sales module is not installed."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        except Exception:
            return Response(
                {"detail": "SalesOrder not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            service = COGSPostingService(sales_order=order, posted_by=request.user)
            results = service.run()
        except COGSPostingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response(
            {
                "lines_posted": len(results),
                "results": [
                    {
                        "product": str(r["line"].product_id),
                        "cogs": r["cogs"],
                        "revenue": r["revenue"],
                        "gross_profit": r["gross_profit"],
                        "cost_source": r["cost_source"],
                        "journal_entry_id": str(r["journal_entry"].id),
                    }
                    for r in results
                ],
            },
            status=status.HTTP_201_CREATED,
        )
