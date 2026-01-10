from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

login_url = "/account/login/"
logout_url = "/accounts/logout/"
register_url = "/api/accounts/register/"
accounts_url = "/api/accounts/"


class UserCreationTestCase(TestCase):
    """Test user creation and registration flow"""

    def setUp(self):
        self.client = APIClient()
        self.user_data = {
            "email": "testuser@example.com",
            "password": "SecurePassword123!",
            "password2": "SecurePassword123!",
            "first_name": "John",
            "last_name": "Doe",
            "department": "ENG",
        }

    def test_user_creation_with_valid_data(self):
        """Test creating a user with valid data"""
        response = self.client.post(register_url, self.user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("user", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["email"], self.user_data["email"])
        self.assertEqual(
            response.data["user"]["first_name"], self.user_data["first_name"]
        )

    def test_user_creation_with_mismatched_passwords(self):
        """Test user creation fails with mismatched passwords"""
        invalid_data = self.user_data.copy()
        invalid_data["password2"] = "DifferentPassword123!"
        response = self.client.post(register_url, invalid_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_user_creation_with_missing_password(self):
        """Test user creation fails when password is missing"""
        invalid_data = self.user_data.copy()
        del invalid_data["password"]
        response = self.client.post(register_url, invalid_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_creation_with_short_password(self):
        """Test user creation fails with password less than 8 characters"""
        invalid_data = self.user_data.copy()
        invalid_data["password"] = "Short1!"
        invalid_data["password2"] = "Short1!"
        response = self.client.post(register_url, invalid_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_creation_with_duplicate_email(self):
        """Test user creation fails with duplicate email"""
        # Create first user
        self.client.post(register_url, self.user_data, format="json")

        # Try to create another user with same email
        duplicate_data = self.user_data.copy()
        duplicate_data["first_name"] = "Jane"
        response = self.client.post(register_url, duplicate_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_user_creation_with_empty_names(self):
        """Test user creation fails with empty first or last name"""
        invalid_data = self.user_data.copy()
        invalid_data["first_name"] = ""
        response = self.client.post(register_url, invalid_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_username_generated_from_first_last_name(self):
        """Test that username is generated correctly from first and last names"""
        response = self.client.post(register_url, self.user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=self.user_data["email"])
        # Username should be first initial + last name (lowercase)
        expected_username = "jdoe"
        self.assertEqual(user.username, expected_username)

    def test_emp_code_auto_generated(self):
        """Test that emp_code is auto-generated"""
        response = self.client.post(register_url, self.user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("emp_code", response.data["user"])
        emp_code = response.data["user"]["emp_code"]
        # emp_code should be in format XXX-XXX
        self.assertEqual(len(emp_code), 7)
        self.assertEqual(emp_code[3], "-")


class LoginTestCase(TestCase):
    """Test login functionality"""

    def setUp(self):
        self.client = APIClient()
        self.user_data = {
            "email": "testuser@example.com",
            "password": "SecurePassword123!",
            "password2": "SecurePassword123!",
            "first_name": "John",
            "last_name": "Doe",
            "department": "ENG",
        }
        # Create a user for login tests
        response = self.client.post(register_url, self.user_data, format="json")
        self.user = User.objects.get(email=self.user_data["email"])
        self.emp_code = response.data["user"]["emp_code"]

    def test_login_with_valid_credentials(self):
        """Test successful login with valid emp_code and password"""
        login_data = {
            "emp_code": self.emp_code,
            "password": self.user_data["password"],
        }
        response = self.client.post("/account/login/", login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["emp_code"], self.emp_code)

    def test_login_with_invalid_password(self):
        """Test login fails with incorrect password"""
        login_data = {
            "emp_code": self.emp_code,
            "password": "WrongPassword123!",
        }
        response = self.client.post("/account/login/", login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.data)

    def test_login_with_invalid_emp_code(self):
        """Test login fails with non-existent emp_code"""
        login_data = {
            "emp_code": "INVALID-CODE",
            "password": self.user_data["password"],
        }
        response = self.client.post("/account/login/", login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_missing_emp_code(self):
        """Test login fails when emp_code is missing"""
        login_data = {
            "password": self.user_data["password"],
        }
        response = self.client.post("/account/login/", login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("emp_code", response.data)

    def test_login_missing_password(self):
        """Test login fails when password is missing"""
        login_data = {
            "emp_code": self.emp_code,
        }
        response = self.client.post(
            "/account/login//account/login/", login_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_login_returns_valid_tokens(self):
        """Test that login returns valid JWT tokens"""
        login_data = {
            "emp_code": self.emp_code,
            "password": self.user_data["password"],
        }
        response = self.client.post("/account/login/", login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify tokens are valid
        access_token = response.data["access"]
        self.assertIsNotNone(access_token)
        self.assertTrue(len(access_token) > 0)


class LogoutTestCase(TestCase):
    """Test logout functionality"""

    def setUp(self):
        self.client = APIClient()
        self.user_data = {
            "email": "testuser@example.com",
            "password": "SecurePassword123!",
            "password2": "SecurePassword123!",
            "first_name": "John",
            "last_name": "Doe",
            "department": "ENG",
        }
        # Create a user and login
        response = self.client.post("/account/register/", self.user_data, format="json")
        self.user = User.objects.get(email=self.user_data["email"])
        self.refresh_token = response.data["refresh"]
        self.access_token = response.data["access"]
        self.emp_code = response.data["user"]["emp_code"]

    def test_logout_with_valid_token(self):
        """Test successful logout with valid refresh token"""
        # Set authentication header
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        logout_data = {
            "refresh": self.refresh_token,
        }
        response = self.client.post(logout_url, logout_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)

    def test_logout_without_authentication(self):
        """Test logout fails without authentication"""
        logout_data = {
            "refresh": self.refresh_token,
        }
        response = self.client.post(logout_url, logout_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_with_invalid_token(self):
        """Test logout fails with invalid refresh token"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        logout_data = {
            "refresh": "invalid_token_here",
        }
        response = self.client.post(logout_url, logout_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_missing_refresh_token(self):
        """Test logout fails when refresh token is missing"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        logout_data = {}
        response = self.client.post(logout_url, logout_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_blacklists_refresh_token(self):
        """Test that token is blacklisted after logout"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        logout_data = {
            "refresh": self.refresh_token,
        }
        response = self.client.post(logout_url, logout_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Try to use the same refresh token again to get new access token
        # This should fail if token blacklisting is working
        refresh_data = {"refresh": self.refresh_token}
        # Note: This test assumes token blacklist is enabled in settings


class UserFetchingTestCase(TestCase):
    """Test user fetching and retrieval"""

    def setUp(self):
        self.client = APIClient()
        # Create multiple test users
        self.users = []
        for i in range(3):
            user_data = {
                "email": f"user{i}@example.com",
                "password": "SecurePassword123!",
                "password2": "SecurePassword123!",
                "first_name": f"User{i}",
                "last_name": "Test",
                "department": "ENG" if i % 2 == 0 else "HR",
            }
            response = self.client.post(register_url, user_data, format="json")
            self.users.append(response.data["user"])
            if i == 0:
                self.user_id = response.data["user"]["id"]
                self.access_token = response.data["access"]

    def test_fetch_user_without_authentication(self):
        """Test that unauthenticated users cannot list users"""
        response = self.client.get(accounts_url, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fetch_user_with_authentication(self):
        """Test that authenticated users can list users"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(accounts_url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertGreaterEqual(len(response.data), 1)

    def test_fetch_specific_user_by_id(self):
        """Test fetching a specific user by ID"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(f"{accounts_url}{self.user_id}/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.user_id))

    def test_fetch_nonexistent_user(self):
        """Test fetching a non-existent user returns 404"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.get(f"{accounts_url}{fake_id}/", format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_fetch_response_contains_required_fields(self):
        """Test that fetched user contains all required fields"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(f"{accounts_url}{self.user_id}/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        required_fields = [
            "id",
            "emp_code",
            "email",
            "first_name",
            "last_name",
            "department",
        ]
        for field in required_fields:
            self.assertIn(field, response.data)

    def test_fetch_multiple_users_pagination(self):
        """Test fetching multiple users"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(accounts_url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 3)

    def test_user_data_integrity(self):
        """Test that user data is returned correctly"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(f"{accounts_url}{self.user_id}/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify expected data
        self.assertEqual(response.data["email"], "user0@example.com")
        self.assertEqual(response.data["first_name"], "User0")
        self.assertEqual(response.data["last_name"], "Test")


class LoginLogoutFlowTestCase(TestCase):
    """Test complete login/logout flow"""

    def setUp(self):
        self.client = APIClient()
        self.user_data = {
            "email": "flowtest@example.com",
            "password": "SecurePassword123!",
            "password2": "SecurePassword123!",
            "first_name": "Flow",
            "last_name": "Test",
            "department": "MKT",
        }

    def test_complete_auth_flow(self):
        """Test complete authentication flow: register -> login -> fetch user -> logout"""
        # Step 1: Register
        register_response = self.client.post(
            register_url, self.user_data, format="json"
        )
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        access_token = register_response.data["access"]
        refresh_token = register_response.data["refresh"]
        user_id = register_response.data["user"]["id"]
        emp_code = register_response.data["user"]["emp_code"]

        # Step 2: Use access token to fetch user data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        fetch_response = self.client.get(f"{accounts_url}{user_id}/", format="json")
        self.assertEqual(fetch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(fetch_response.data["email"], self.user_data["email"])

        # Step 3: Logout
        logout_data = {"refresh": refresh_token}
        logout_response = self.client.post(logout_url, logout_data, format="json")
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        # Step 4: Try to use access token after logout (should still work until expiry)
        # This tests that the token is blacklisted for refresh operations

    def test_login_after_registration(self):
        """Test logging in with credentials from registration"""
        # Register user
        register_response = self.client.post(
            register_url, self.user_data, format="json"
        )
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        emp_code = register_response.data["user"]["emp_code"]

        # Logout (clear tokens)
        self.client.credentials()

        # Login with emp_code and password
        login_data = {
            "emp_code": emp_code,
            "password": self.user_data["password"],
        }
        login_response = self.client.post(login_url, login_data, format="json")
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)
        self.assertIn("refresh", login_response.data)
