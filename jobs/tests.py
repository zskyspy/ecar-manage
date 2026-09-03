from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from .models import UserProfile


class AuthAndRoleTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create owner user
        self.owner_user = User.objects.create_user(
            username="owner_user",
            password="OwnerPassword123!",
            email="owner@garageflow.local",
        )
        self.owner_user.profile.role = UserProfile.Role.OWNER
        self.owner_user.profile.save()

        # Create technician user
        self.tech_user = User.objects.create_user(
            username="tech_user",
            password="TechPassword123!",
            email="tech@garageflow.local",
        )
        self.tech_user.profile.role = UserProfile.Role.TECHNICIAN
        self.tech_user.profile.save()

    def test_user_profile_auto_created(self):
        """Verify that creating a user automatically creates an associated UserProfile."""
        new_user = User.objects.create_user(
            username="test_auto_user",
            password="Password123!",
        )
        self.assertTrue(hasattr(new_user, "profile"))
        self.assertEqual(new_user.profile.role, UserProfile.Role.TECHNICIAN)
        self.assertTrue(new_user.profile.is_technician)
        self.assertFalse(new_user.profile.is_owner)

    def test_token_obtain_pair_contains_custom_claims(self):
        """Verify that /api/token/ returns tokens and embeds user role and username."""
        url = reverse("token_obtain_pair")
        response = self.client.post(
            url,
            {"username": "owner_user", "password": "OwnerPassword123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["username"], "owner_user")
        self.assertEqual(response.data["role"], "owner")

        # Decode token to verify custom payload claims
        token = AccessToken(response.data["access"])
        self.assertEqual(token["username"], "owner_user")
        self.assertEqual(token["role"], "owner")

    def test_current_user_me_endpoint(self):
        """Verify /api/auth/me/ returns user details and role with bearer token."""
        url = reverse("current_user")

        # Unauthenticated request should fail with 401
        res_unauth = self.client.get(url)
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticated with owner
        self.client.force_authenticate(user=self.owner_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "owner_user")
        self.assertEqual(response.data["profile"]["role"], "owner")

    def test_owner_only_endpoint_permissions(self):
        """Verify only users with the owner role can access owner test endpoint."""
        url = reverse("test_owner_role")

        # Unauthenticated request -> 401
        self.client.logout()
        res_unauth = self.client.get(url)
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # Technician request -> 403 Forbidden
        self.client.force_authenticate(user=self.tech_user)
        res_tech = self.client.get(url)
        self.assertEqual(res_tech.status_code, status.HTTP_403_FORBIDDEN)

        # Owner request -> 200 OK
        self.client.force_authenticate(user=self.owner_user)
        res_owner = self.client.get(url)
        self.assertEqual(res_owner.status_code, status.HTTP_200_OK)
        self.assertIn("access granted", res_owner.data["message"])

    def test_technician_only_endpoint_permissions(self):
        """Verify only users with technician role can access technician test endpoint."""
        url = reverse("test_technician_role")

        # Unauthenticated request -> 401
        self.client.logout()
        res_unauth = self.client.get(url)
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # Owner request -> 403 Forbidden
        self.client.force_authenticate(user=self.owner_user)
        res_owner = self.client.get(url)
        self.assertEqual(res_owner.status_code, status.HTTP_403_FORBIDDEN)

        # Technician request -> 200 OK
        self.client.force_authenticate(user=self.tech_user)
        res_tech = self.client.get(url)
        self.assertEqual(res_tech.status_code, status.HTTP_200_OK)
        self.assertIn("access granted", res_tech.data["message"])
