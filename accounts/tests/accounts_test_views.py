from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()


class AccountsAPITests(APITestCase):
    """Test suite for the accounts API endpoints"""

    def setUp(self):
        """Set up tests data"""
        # Create a tests user for authentication tests
        self.test_user = User.objects.create_user(
            username='testuser',
            email='tests@example.com',
            password='TestPassword123'
        )

        # API endpoints
        self.register_url = reverse('accounts-register')
        self.login_url = reverse('token_obtain_pair')
        self.profile_url = reverse('accounts-profile')
        self.refresh_url = reverse('token_refresh')

        # Sample registration data
        self.valid_registration_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'NewUserPass123',
            'password2': 'NewUserPass123',
            'first_name': 'New',
            'last_name': 'User'
        }

        # Sample login data
        self.valid_login_data = {
            'username': 'testuser',
            'password': 'TestPassword123'
        }

    def test_user_registration(self):
        """Test user registration endpoint"""
        response = self.client.post(self.register_url, self.valid_registration_data)

        # Check status code
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check user was created in database
        self.assertTrue(User.objects.filter(username='newuser').exists())

        # Check returned data
        self.assertEqual(response.data['username'], 'newuser')
        self.assertEqual(response.data['email'], 'newuser@example.com')
        self.assertEqual(response.data['first_name'], 'New')
        self.assertEqual(response.data['last_name'], 'User')
        self.assertEqual(response.data['score'], 0)  # Default score

        # Ensure password is not in response
        self.assertNotIn('password', response.data)

    def test_user_registration_invalid_data(self):
        """Test registration with invalid data"""
        # Test with mismatched passwords
        invalid_data = self.valid_registration_data.copy()
        invalid_data['password2'] = 'DifferentPassword123'

        response = self.client.post(self.register_url, invalid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test with existing username
        invalid_data = self.valid_registration_data.copy()
        invalid_data['username'] = 'testuser'  # Already exists

        response = self.client.post(self.register_url, invalid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_login(self):
        """Test user login and JWT token generation"""
        response = self.client.post(self.login_url, self.valid_login_data)

        # Check status code
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check response contains tokens
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        # Save access token for later tests
        self.access_token = response.data['access']

    def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        invalid_data = self.valid_login_data.copy()
        invalid_data['password'] = 'WrongPassword123'

        response = self.client.post(self.login_url, invalid_data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_user_profile(self):
        """Test retrieving user profile"""
        # Login first to get token
        login_response = self.client.post(self.login_url, self.valid_login_data)
        token = login_response.data['access']

        # Set authentication header
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Get profile
        response = self.client.get(self.profile_url)

        # Check status code
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check returned data
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['email'], 'tests@example.com')

    def test_get_profile_unauthenticated(self):
        """Test profile access without authentication"""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_profile(self):
        """Test updating user profile"""
        # Login first
        login_response = self.client.post(self.login_url, self.valid_login_data)
        token = login_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Update data
        update_data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }

        response = self.client.patch(self.profile_url, update_data)

        # Check status code
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check data was updated
        self.assertEqual(response.data['first_name'], 'Updated')
        self.assertEqual(response.data['last_name'], 'Name')

        # Verify database was updated
        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.first_name, 'Updated')
        self.assertEqual(self.test_user.last_name, 'Name')

    def test_token_refresh(self):
        """Test JWT token refresh"""
        # Login first to get tokens
        login_response = self.client.post(self.login_url, self.valid_login_data)
        refresh_token = login_response.data['refresh']

        # Attempt to refresh the token
        response = self.client.post(self.refresh_url, {'refresh': refresh_token})

        # Check status code
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check new access token was returned
        self.assertIn('access', response.data)