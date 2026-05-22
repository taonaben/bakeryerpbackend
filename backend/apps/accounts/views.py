import logging
from rest_framework import viewsets, status, generics
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    BasePermission,
)
from django.contrib.auth import get_user_model, authenticate
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetResponseSerializer,
    StaffPasswordResetSerializer,
)
from rest_framework.parsers import JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from .filters import UserFilter
from .permissions import (
    ModulePermission,
)
from .services import (
    change_own_password,
    delete_user,
    get_company_user_queryset,
    is_self_edit,
    override_user_password,
    update_user,
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
    queryset = User.objects.select_related("company").all()
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_class = UserFilter
    ordering_fields = [
        "emp_code",
        "email",
        "first_name",
        "last_name",
        "username",
        "role",
        "is_active",
        "is_staff",
        "date_joined",
    ]
    search_fields = [
        "emp_code",
        "email",
        "first_name",
        "last_name",
        "username",
        "role",
    ]
    # permission_classes = [IsAuthenticatedOrCreate]

    def get_queryset(self):
        if self.action == "list" and not self.request.user.is_authenticated:
            return User.objects.none()
        if self.action in ["create", "register"]:
            return self.queryset
        return get_company_user_queryset(self.request.user)

    def get_serializer_class(self):
        if self.action in ["create", "register"]:
            return UserCreateSerializer
        if self.action == "change_password":
            return PasswordChangeSerializer
        if self.action == "reset_password":
            return StaffPasswordResetSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ["create", "register"]:
            return [AllowAny()]
        elif self.action in [
            "list",
            "retrieve",
            "me",
            "change_password",
            "destroy",
            "update",
            "partial_update",
            "reset_password",
        ]:
            return [IsAuthenticated()]
        return [IsAuthenticated(), UsersPermission()]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Retrieve details of the currently authenticated user"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

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

    def update(self, request, *args, **kwargs):
        """Update a user through the account service rules."""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        if is_self_edit(request.user, instance):
            partial = True

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        user = update_user(request.user, instance, serializer.validated_data)
        return Response(UserSerializer(user, context=self.get_serializer_context()).data)

    def destroy(self, request, *args, **kwargs):
        """Delete a user through the account service rules."""
        instance = self.get_object()
        delete_user(request.user, instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=PasswordChangeSerializer,
        responses=PasswordResetResponseSerializer,
    )
    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        """Change the current user's password after checking the old password."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_own_password(
            request.user,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response(
            {
                "detail": "Password changed successfully.",
                "user_id": request.user.id,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=StaffPasswordResetSerializer,
        responses=PasswordResetResponseSerializer,
    )
    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        """Override a company user's password for IT/account admins."""
        target_user = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        override_user_password(
            request.user,
            target_user,
            serializer.validated_data["new_password"],
        )
        return Response(
            {
                "detail": "Password reset successfully.",
                "user_id": target_user.id,
            },
            status=status.HTTP_200_OK,
        )


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
