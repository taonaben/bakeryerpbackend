from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from ..models import Product, Warehouse
from ..services.batch_retrieval import create_stock_movement_with_policy
from ..serializers import StockMovementSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_movement_with_policy_view(request):
    """
    Create a stock movement using retrieval policy (FIFO/LIFO/FEFO).
    Automatically selects and distributes across batches as needed.

    Expected payload:\n
    {\n
        "product_id": "uuid",\n
        "warehouse_id": "uuid",\n
        "movement_type": "OUT|IN|ADJUSTMENT|RETURN",\n
        "quantity": 50,\n
        "reference_number": "optional",\n
        "notes": "optional"\n
    }
    """
    try:
        product = Product.objects.get(id=request.data["product_id"])
        warehouse = Warehouse.objects.get(id=request.data["warehouse_id"])

        movement = create_stock_movement_with_policy(
            product=product,
            warehouse=warehouse,
            movement_type=request.data["movement_type"],
            quantity=float(request.data["quantity"]),
            reference=request.data.get("reference_number"),
            notes=request.data.get("notes"),
        )

        serializer = StockMovementSerializer(movement)
        return Response(
            {
                "message": "Stock movement created successfully",
                "movement": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    except (Product.DoesNotExist, Warehouse.DoesNotExist):
        return Response(
            {"error": "Product or Warehouse not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except ValidationError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except KeyError as e:
        return Response(
            {"error": f"Missing required field: {e}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
