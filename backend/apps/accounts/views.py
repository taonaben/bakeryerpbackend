import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from django.contrib.auth import get_user_model, authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    LoginSerializer,
    LogoutSerializer,
)
from rest_framework.parsers import JSONParser
from rest_framework.views import APIView

User = get_user_model()
logger = logging.getLogger(__name__)


class IsAuthenticatedOrCreate(BasePermission):
    """Allow unauthenticated access for create/register, authenticated for others"""

    def has_permission(self, request, view):
        if view.action in ["create", "register"]:
            return True
        return request.user.is_authenticated


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticatedOrCreate]

    def get_queryset(self):
        if self.action == "list" and not self.request.user.is_authenticated:
            return User.objects.none()
        return User.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    # TODO: fix permission classes for register action
    @action(detail=False, methods=["post"])
    def register(self, request):
        """Register a new user with profile details"""
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "user": UserSerializer(user).data,
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_201_CREATED,
            )
        logger.warning(f"Registration failed for email: {request.data.get('email', 'unknown')} - {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


#! AUTHENTICATION VIEWS


class LoginView(APIView):
    """Handle user login and return JWT tokens"""

    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        emp_code = serializer.validated_data.get("emp_code")
        password = serializer.validated_data.get("password")

        # Find user by emp_code to get username for authentication
        try:
            user_obj = get_user_model().objects.get(emp_code=emp_code)
            user = authenticate(username=user_obj.username, password=password)
        except get_user_model().DoesNotExist:
            user = None

        if user:
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "emp_code": user.emp_code,
                    },
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED
        )


class LogoutView(APIView):
    """Handle user logout"""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        try:
            serializer = LogoutSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            refresh_token = serializer.validated_data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"detail": "Logout successful."},
                status=status.HTTP_200_OK,
            )
        except TokenError:
            return Response(
                {"detail": "Invalid token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
