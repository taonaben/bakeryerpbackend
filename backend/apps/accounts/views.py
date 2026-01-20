import logging
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    BasePermission,
    IsAdminUser,
)
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
from .permissions import (
    ModulePermission,
)


User = get_user_model()
logger = logging.getLogger(__name__)


class IsAuthenticatedOrCreate(BasePermission):
    """Allow unauthenticated access for create/register, authenticated for others"""

    def has_permission(self, request, view):
        if view.action in ["create", "register"]:
            return True
        return request.user.is_authenticated


class UsersPermission(ModulePermission):
    module = "users"


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user accounts and registration.

    Supports user registration, viewing, and management operations.

    Permissions:\n
        - create/register: Allow any (public registration)\n
        - list: Allow any (public access)\n
        - retrieve: Authenticated users only\n
        - update/delete: Admin users only\n
    Custom actions:\n
        - register: Create new user account with profile details
    """

    serializer_class = UserSerializer
    # permission_classes = [IsAuthenticatedOrCreate]

    def get_queryset(self):
        if self.action == "list" and not self.request.user.is_authenticated:
            return User.objects.none()
        return User.objects.all()

    def get_serializer_class(self):
        if self.action in ["create", "register"]:
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ["create", "register"]:
            return [AllowAny()]
        elif self.action == "list":
            # return [ UsersPermission()]
            return [AllowAny()]  # Temporary open list view
        elif self.action in ["destroy", "update", "partial_update"]:
            return [IsAdminUser()]
        elif self.action == "retrieve":
            return [IsAuthenticated(), UsersPermission()]
        return [IsAuthenticated(), UsersPermission()]

    @action(detail=False, methods=["post"])
    def register(self, request):
        """Register a new user with profile details"""
        serializer = self.get_serializer(data=request.data)
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
        logger.warning(
            f"Registration failed for email: {request.data.get('email', 'unknown')} - {serializer.errors}"
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


#! AUTHENTICATION VIEWS


class LoginView(generics.GenericAPIView):
    """
    Handle user authentication and JWT token generation.

    Authenticates users using employee code and password.

    Request body:\n
        - emp_code: Employee code (required)\n
        - password: User password (required)\n
    Response:\n
        - refresh: JWT refresh token\n
        - access: JWT access token\n
        - user: Basic user information (id, username, emp_code)
    """

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request, *args, **kwargs):
        """Authenticate user and return JWT tokens"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        emp_code = serializer.validated_data.get("emp_code")
        password = serializer.validated_data.get("password")

        try:
            user_obj = User.objects.get(emp_code=emp_code)
            user = authenticate(username=user_obj.username, password=password)
        except User.DoesNotExist:
            logger.warning(f"Login attempt with non-existent emp_code: {emp_code}")
            user = None

        if user is None:
            logger.warning(f"Failed login attempt for emp_code: {emp_code}")
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "emp_code": user.emp_code,
                },
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(generics.GenericAPIView):
    """
    Handle user logout by blacklisting JWT refresh tokens.

    Requires authentication to access this endpoint.

    Request body:\n
        - refresh: JWT refresh token to blacklist (required)\n
    Response:\n
        - detail: Success or error message
    """

    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, *args, **kwargs):
        """Blacklist refresh token and logout user"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data.get("refresh")

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info(f"User {request.user.username} logged out successfully")
            return Response(
                {"detail": "Logout successful."},
                status=status.HTTP_200_OK,
            )
        except TokenError as e:
            logger.error(
                f"Token blacklist error for user {request.user.username}: {str(e)}"
            )
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Unexpected error during logout: {str(e)}")
            return Response(
                {"detail": "An error occurred during logout."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
