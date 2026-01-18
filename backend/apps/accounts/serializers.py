from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from apps.accounts import models
import uuid

User = get_user_model()


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for user generation"""

    password = serializers.CharField(write_only=True, required=True, min_length=8)
    password2 = serializers.CharField(write_only=True, required=True, min_length=8)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = [
            "emp_code",
            "email",
            "password",
            "password2",
            "first_name",
            "last_name",
            "department",
        ]
        read_only_fields = ["emp_code"]

    def validate(self, data):
        if data.get("password") != data.get("password2"):
            raise serializers.ValidationError({"password": "Passwords do not match."})

        # Validate names are not empty
        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        if not first_name or not last_name:
            raise serializers.ValidationError(
                {"first_name": "First and last names cannot be empty."}
            )

        return data

    def create(self, validated_data):
        # Extract profile and related data
        validated_data.pop("password2")
        password = validated_data.pop("password")
        first_name = validated_data.pop("first_name").strip()
        last_name = validated_data.pop("last_name").strip()

        # Generate username from first and last name with uniqueness guarantee
        base_username = f"{first_name[0].lower()}{last_name.lower()}".replace(" ", "")
        username = base_username
        counter = 1

        # Ensure username is unique
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # Create user
        try:
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
                **validated_data,
            )
            return user
        except Exception as e:
            raise serializers.ValidationError(f"Failed to create user: {str(e)}")


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details"""

    class Meta:
        model = User
        fields = [
            "id",
            "emp_code",
            "email",
            "first_name",
            "last_name",
            "username",
            "department",
            "is_active",
            "is_staff",
            "date_joined",
        ]


class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""

    emp_code = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)


class LogoutSerializer(serializers.Serializer):
    """Serializer for user logout"""

    refresh = serializers.CharField(required=True)
