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


class JobCrudTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="test_user",
            password="Password123!",
        )
        self.client.force_authenticate(user=self.user)

        self.job_data = {
            "customer_name": "Alice Smith",
            "customer_phone": "07123456789",
            "vehicle_make": "Ford",
            "vehicle_model": "Focus",
            "vehicle_year": 2019,
            "license_plate": "AB19 CDE",
            "vin": "WF0AXXWPGAY123456",
            "description": "Brake pads replacement and oil change",
            "status": "pending",
        }

    def test_create_job(self):
        """Verify POST /api/jobs/ creates a job with created_by set to request.user."""
        url = reverse("job-list")
        response = self.client.post(url, self.job_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["customer_name"], "Alice Smith")
        self.assertEqual(response.data["license_plate"], "AB19 CDE")
        self.assertEqual(response.data["created_by_name"], "test_user")

    def test_list_jobs(self):
        """Verify GET /api/jobs/ lists all jobs."""
        from .models import Job

        Job.objects.create(created_by=self.user, **self.job_data)
        url = reverse("job-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_retrieve_job(self):
        """Verify GET /api/jobs/{id}/ returns single job details."""
        from .models import Job

        job = Job.objects.create(created_by=self.user, **self.job_data)
        url = reverse("job-detail", kwargs={"pk": job.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], job.id)
        self.assertEqual(response.data["vehicle_model"], "Focus")

    def test_partial_update_job(self):
        """Verify PATCH /api/jobs/{id}/ updates status and fields."""
        from .models import Job

        job = Job.objects.create(created_by=self.user, **self.job_data)
        url = reverse("job-detail", kwargs={"pk": job.id})
        update_data = {"status": "in_progress", "description": "Brake pads completed, working on oil"}
        response = self.client.patch(url, update_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "in_progress")
        self.assertEqual(response.data["description"], "Brake pads completed, working on oil")

    def test_delete_job(self):
        """Verify DELETE /api/jobs/{id}/ removes the job."""
        from .models import Job

        job = Job.objects.create(created_by=self.user, **self.job_data)
        url = reverse("job-detail", kwargs={"pk": job.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Job.objects.filter(id=job.id).exists())

    def test_filter_jobs_by_status(self):
        """Verify filtering jobs by ?status=in_progress."""
        from .models import Job

        job_pending = dict(self.job_data)
        job_pending["status"] = Job.Status.PENDING
        Job.objects.create(**job_pending)

        job_in_prog = dict(self.job_data)
        job_in_prog["status"] = Job.Status.IN_PROGRESS
        job_in_prog["license_plate"] = "XY20 ZZZ"
        Job.objects.create(**job_in_prog)

        url = f"{reverse('job-list')}?status=in_progress"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["license_plate"], "XY20 ZZZ")

    def test_search_jobs(self):
        """Verify searching jobs by ?search=..."""
        from .models import Job

        job_search = dict(self.job_data)
        job_search["customer_name"] = "Robert Taylor"
        Job.objects.create(**job_search)

        url = f"{reverse('job-list')}?search=Robert"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["customer_name"], "Robert Taylor")


class JobAssignmentTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Owner
        self.owner = User.objects.create_user(
            username="shop_owner",
            password="OwnerPassword123!",
        )
        self.owner.profile.role = UserProfile.Role.OWNER
        self.owner.profile.save()

        # Create Technician
        self.technician = User.objects.create_user(
            username="shop_tech",
            password="TechPassword123!",
        )
        self.technician.profile.role = UserProfile.Role.TECHNICIAN
        self.technician.profile.save()

        # Create another Owner
        self.other_owner = User.objects.create_user(
            username="other_owner",
            password="OwnerPassword123!",
        )
        self.other_owner.profile.role = UserProfile.Role.OWNER
        self.other_owner.profile.save()

        # Create Job
        from .models import Job

        self.job = Job.objects.create(
            customer_name="John Doe",
            license_plate="JD10 ABC",
            vehicle_make="Audi",
            vehicle_model="A4",
            description="Clutch inspection",
            created_by=self.owner,
        )

    def test_owner_can_assign_technician(self):
        """Owner can successfully assign a technician to a job."""
        self.client.force_authenticate(user=self.owner)
        url = reverse("job-assign", kwargs={"pk": self.job.id})
        response = self.client.post(url, {"technician_id": self.technician.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["assigned_technician"], self.technician.id)
        self.assertEqual(response.data["assigned_technician_name"], "shop_tech")

        self.job.refresh_from_db()
        self.assertEqual(self.job.assigned_technician, self.technician)

    def test_owner_can_unassign_technician(self):
        """Owner can unassign a technician by passing technician_id: null."""
        self.job.assigned_technician = self.technician
        self.job.save()

        self.client.force_authenticate(user=self.owner)
        url = reverse("job-assign", kwargs={"pk": self.job.id})
        response = self.client.post(url, {"technician_id": None}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["assigned_technician"])
        self.assertIsNone(response.data["assigned_technician_name"])

        self.job.refresh_from_db()
        self.assertIsNone(self.job.assigned_technician)

    def test_technician_cannot_assign(self):
        """Technician calling the assign endpoint receives 403 Forbidden."""
        self.client.force_authenticate(user=self.technician)
        url = reverse("job-assign", kwargs={"pk": self.job.id})
        response = self.client.post(url, {"technician_id": self.technician.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assign_non_existent_user_fails(self):
        """Assigning a non-existent user id returns 400 Bad Request."""
        self.client.force_authenticate(user=self.owner)
        url = reverse("job-assign", kwargs={"pk": self.job.id})
        response = self.client.post(url, {"technician_id": 99999}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("technician_id", response.data)

    def test_assign_non_technician_user_fails(self):
        """Assigning a user who has the owner role returns 400 Bad Request."""
        self.client.force_authenticate(user=self.owner)
        url = reverse("job-assign", kwargs={"pk": self.job.id})
        response = self.client.post(url, {"technician_id": self.other_owner.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("technician_id", response.data)

    def test_unauthenticated_cannot_assign(self):
        """Anonymous requests to assign endpoint receive 401 Unauthorized."""
        url = reverse("job-assign", kwargs={"pk": self.job.id})
        response = self.client.post(url, {"technician_id": self.technician.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


