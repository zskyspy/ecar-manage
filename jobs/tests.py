from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from .models import Department, UserProfile


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
        self.user.profile.role = UserProfile.Role.OWNER
        self.user.profile.save()
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
        self.technician.profile.department = Department.MECHANICAL
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


class StatusUpdateTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Owner
        self.owner = User.objects.create_user(
            username="owner_user",
            password="OwnerPassword123!",
        )
        self.owner.profile.role = UserProfile.Role.OWNER
        self.owner.profile.save()

        # Create Assigned Technician
        self.assigned_tech = User.objects.create_user(
            username="assigned_tech",
            password="TechPassword123!",
        )
        self.assigned_tech.profile.role = UserProfile.Role.TECHNICIAN
        self.assigned_tech.profile.department = Department.MECHANICAL
        self.assigned_tech.profile.save()

        # Create Unassigned Technician
        self.unassigned_tech = User.objects.create_user(
            username="unassigned_tech",
            password="TechPassword123!",
        )
        self.unassigned_tech.profile.role = UserProfile.Role.TECHNICIAN
        self.unassigned_tech.profile.department = Department.MECHANICAL
        self.unassigned_tech.profile.save()

        # Create Job
        from .models import Job

        self.job = Job.objects.create(
            customer_name="Michael Scott",
            license_plate="DM01 PAP",
            vehicle_make="Chrysler",
            vehicle_model="Sebring",
            description="Convertible top replacement",
            status=Job.Status.PENDING,
            assigned_technician=self.assigned_tech,
            created_by=self.owner,
        )

    def test_assigned_tech_can_post_status_update(self):
        """Assigned technician can post an update; parent job status is updated."""
        from .models import Job, StatusUpdate

        self.client.force_authenticate(user=self.assigned_tech)
        url = reverse("job-status-updates", kwargs={"pk": self.job.id})
        payload = {
            "status": "in_progress",
            "note": "Disassembled old roof frame",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "in_progress")
        self.assertEqual(response.data["note"], "Disassembled old roof frame")
        self.assertEqual(response.data["technician_name"], "assigned_tech")

        # Verify parent job was updated
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.IN_PROGRESS)

        # Verify StatusUpdate in DB
        self.assertEqual(StatusUpdate.objects.filter(job=self.job).count(), 1)

    def test_unassigned_tech_cannot_post_status_update(self):
        """Unassigned technician receives 403 Forbidden when trying to update status."""
        from .models import Job

        self.client.force_authenticate(user=self.unassigned_tech)
        url = reverse("job-status-updates", kwargs={"pk": self.job.id})
        payload = {"status": "completed", "note": "Trying to update someone else's job"}
        response = self.client.post(url, payload, format="json")

        # Under query-level scoping, unassigned technician gets 404 Not Found (or 403 Forbidden)
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.PENDING)


    def test_owner_cannot_post_status_update_directly(self):
        """Owner receives 403 Forbidden on the technician status-update endpoint."""
        from .models import Job

        self.client.force_authenticate(user=self.owner)
        url = reverse("job-status-updates", kwargs={"pk": self.job.id})
        payload = {"status": "completed", "note": "Owner attempting direct status post"}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.PENDING)

    def test_unauthenticated_cannot_post_status_update(self):
        """Anonymous user receives 401 Unauthorized."""
        url = reverse("job-status-updates", kwargs={"pk": self.job.id})
        payload = {"status": "in_progress", "note": "Anonymous attempt"}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_status_history(self):
        """Any authenticated user can retrieve the chronological status update history."""
        from .models import StatusUpdate

        StatusUpdate.objects.create(
            job=self.job,
            status="in_progress",
            note="Started inspection",
            technician=self.assigned_tech,
        )
        StatusUpdate.objects.create(
            job=self.job,
            status="waiting_parts",
            note="Waiting for hydraulic pump",
            technician=self.assigned_tech,
        )

        self.client.force_authenticate(user=self.owner)
        url = reverse("job-status-updates", kwargs={"pk": self.job.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["status"], "in_progress")
        self.assertEqual(response.data[1]["status"], "waiting_parts")

    def test_invalid_status_rejected(self):
        """Submitting an unrecognized status value returns 400 Bad Request."""
        self.client.force_authenticate(user=self.assigned_tech)
        url = reverse("job-status-updates", kwargs={"pk": self.job.id})
        payload = {"status": "invalid_status_xyz", "note": "bad status"}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)


class RoleScopedViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Owner
        self.owner = User.objects.create_user(
            username="scoped_owner",
            password="OwnerPassword123!",
        )
        self.owner.profile.role = UserProfile.Role.OWNER
        self.owner.profile.save()

        # Create Technician A
        self.tech_a = User.objects.create_user(
            username="tech_a",
            password="TechPassword123!",
        )
        self.tech_a.profile.role = UserProfile.Role.TECHNICIAN
        self.tech_a.profile.department = Department.MECHANICAL
        self.tech_a.profile.save()

        # Create Technician B
        self.tech_b = User.objects.create_user(
            username="tech_b",
            password="TechPassword123!",
        )
        self.tech_b.profile.role = UserProfile.Role.TECHNICIAN
        self.tech_b.profile.department = Department.MECHANICAL
        self.tech_b.profile.save()

        from .models import Job

        # Job 1: Unassigned
        self.job_unassigned = Job.objects.create(
            customer_name="Customer 1",
            license_plate="UN11 AAA",
            vehicle_make="Toyota",
            vehicle_model="Yaris",
            description="Inspection",
            assigned_technician=None,
            created_by=self.owner,
        )

        # Job 2: Assigned to Tech A
        self.job_tech_a = Job.objects.create(
            customer_name="Customer 2",
            license_plate="TA22 AAA",
            vehicle_make="Honda",
            vehicle_model="Civic",
            description="Brake pads",
            assigned_technician=self.tech_a,
            created_by=self.owner,
        )

        # Job 3: Assigned to Tech B
        self.job_tech_b = Job.objects.create(
            customer_name="Customer 3",
            license_plate="TB33 BBB",
            vehicle_make="Nissan",
            vehicle_model="Micra",
            description="Oil change",
            assigned_technician=self.tech_b,
            created_by=self.owner,
        )

    def test_owner_sees_all_jobs(self):
        """Owner can see all jobs: unassigned, tech A, and tech B."""
        self.client.force_authenticate(user=self.owner)
        url = reverse("job-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        job_ids = [item["id"] for item in response.data]
        self.assertIn(self.job_unassigned.id, job_ids)
        self.assertIn(self.job_tech_a.id, job_ids)
        self.assertIn(self.job_tech_b.id, job_ids)

    def test_technician_sees_only_assigned_jobs(self):
        """Technician A can only see jobs assigned to Tech A."""
        self.client.force_authenticate(user=self.tech_a)
        url = reverse("job-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.job_tech_a.id)

    def test_technician_b_sees_only_assigned_jobs(self):
        """Technician B can only see jobs assigned to Tech B."""
        self.client.force_authenticate(user=self.tech_b)
        url = reverse("job-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.job_tech_b.id)

    def test_technician_cannot_retrieve_unassigned_job(self):
        """Technician receives 404 when querying detail of an unassigned job."""
        self.client.force_authenticate(user=self.tech_a)
        url = reverse("job-detail", kwargs={"pk": self.job_unassigned.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_technician_cannot_retrieve_other_technician_job(self):
        """Technician A receives 404 when querying detail of Tech B's job."""
        self.client.force_authenticate(user=self.tech_a)
        url = reverse("job-detail", kwargs={"pk": self.job_tech_b.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_retrieve_any_job(self):
        """Owner can retrieve any job detail."""
        self.client.force_authenticate(user=self.owner)
        for job_obj in (self.job_unassigned, self.job_tech_a, self.job_tech_b):
            url = reverse("job-detail", kwargs={"pk": job_obj.id})
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["id"], job_obj.id)


class FrontendViewTests(TestCase):
    """Tests for Step 10: Django template-based frontend views and auth routing."""

    def setUp(self):
        from django.test import Client
        self.client = Client()

        # Create Owner
        self.owner = User.objects.create_user(
            username="fe_owner", password="OwnerFE123!"
        )
        self.owner.profile.role = UserProfile.Role.OWNER
        self.owner.profile.save()

        # Create Technician
        self.tech = User.objects.create_user(
            username="fe_tech", password="TechFE123!"
        )
        self.tech.profile.role = UserProfile.Role.TECHNICIAN
        self.tech.profile.department = Department.ELECTRONIC
        self.tech.profile.save()

    def test_login_page_renders(self):
        """GET /login/ returns 200 with a login form."""
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ECAR Space")


    def test_unauthenticated_dashboard_redirects_to_login(self):
        """Unauthenticated user visiting /dashboard/ is redirected to login."""
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, "/login/?next=/dashboard/", fetch_redirect_response=False)

    def test_unauthenticated_owner_portal_redirects_to_login(self):
        """Unauthenticated user visiting /owner/ is redirected to login."""
        response = self.client.get(reverse("owner_dashboard"))
        self.assertRedirects(response, "/login/?next=/owner/", fetch_redirect_response=False)

    def test_unauthenticated_tech_portal_redirects_to_login(self):
        """Unauthenticated user visiting /tech/ is redirected to login."""
        response = self.client.get(reverse("tech_dashboard"))
        self.assertRedirects(response, "/login/?next=/tech/", fetch_redirect_response=False)

    def test_owner_dashboard_redirect(self):
        """Authenticated owner visiting /dashboard/ is redirected to /owner/."""
        self.client.login(username="fe_owner", password="OwnerFE123!")
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, "/owner/", fetch_redirect_response=False)

    def test_tech_dashboard_redirect(self):
        """Authenticated technician visiting /dashboard/ is redirected to /tech/."""
        self.client.login(username="fe_tech", password="TechFE123!")
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, "/tech/", fetch_redirect_response=False)

    def test_owner_can_access_owner_portal(self):
        """Owner visiting /owner/ is redirected to /owner/electronic/ (the electronic job list)."""
        self.client.login(username="fe_owner", password="OwnerFE123!")
        response = self.client.get(reverse("owner_dashboard"))
        self.assertRedirects(response, "/owner/electronic/", fetch_redirect_response=False)

    def test_tech_can_access_tech_portal(self):
        """Technician visiting /tech/ gets 200 OK."""
        self.client.login(username="fe_tech", password="TechFE123!")
        response = self.client.get(reverse("tech_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_tech_cannot_access_owner_portal(self):
        """Technician visiting /owner/ is forbidden (403)."""
        self.client.login(username="fe_tech", password="TechFE123!")
        response = self.client.get(reverse("owner_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_owner_cannot_access_tech_portal(self):
        """Owner visiting /tech/ is forbidden (403)."""
        self.client.login(username="fe_owner", password="OwnerFE123!")
        response = self.client.get(reverse("tech_dashboard"))
        self.assertEqual(response.status_code, 403)


class OwnerFrontendTests(TestCase):
    """Tests for Step 11: Owner Frontend CRUD Views."""

    def setUp(self):
        from django.test import Client
        from .models import Job

        self.client = Client()

        # Owner
        self.owner = User.objects.create_user(username="crud_owner", password="CrudOwner1!")
        self.owner.profile.role = UserProfile.Role.OWNER
        self.owner.profile.save()

        # Technician
        self.tech = User.objects.create_user(username="crud_tech", password="CrudTech1!")
        self.tech.profile.role = UserProfile.Role.TECHNICIAN
        self.tech.profile.department = Department.MECHANICAL
        self.tech.profile.save()

        # Pre-existing job
        self.job = Job.objects.create(
            customer_name="Test Customer",
            license_plate="TC01 XYZ",
            vehicle_make="Ford",
            vehicle_model="Focus",
            description="Annual service",
            department=Department.MECHANICAL,
            created_by=self.owner,
        )
        self.client.login(username="crud_owner", password="CrudOwner1!")

    def test_job_list_accessible_by_owner(self):
        """GET /owner/mechanical/ returns 200 for owner."""
        response = self.client.get(reverse("owner_department_jobs", args=["mechanical"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TC01 XYZ")

    def test_job_list_blocked_for_technician(self):
        """GET /owner/mechanical/ returns 403 for technician."""
        self.client.login(username="crud_tech", password="CrudTech1!")
        response = self.client.get(reverse("owner_department_jobs", args=["mechanical"]))
        self.assertEqual(response.status_code, 403)

    def test_job_create_get(self):
        """GET /owner/electronic/create/ renders the create form."""
        response = self.client.get(reverse("owner_department_job_create", args=["electronic"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create New Repair Job")

    def test_job_create_post(self):
        """POST /owner/electronic/create/ creates a job and redirects to detail."""
        from .models import Job
        count_before = Job.objects.count()
        response = self.client.post(reverse("owner_department_job_create", args=["electronic"]), {
            "customer_name": "New Customer",
            "customer_phone": "07700900123",
            "license_plate": "NEW1 AAA",
            "vehicle_make": "BMW",
            "vehicle_model": "3 Series",
            "description": "Tyre replacement",
        })
        self.assertEqual(Job.objects.count(), count_before + 1)
        new_job = Job.objects.latest("created_at")
        self.assertEqual(new_job.department, "electronic")
        self.assertRedirects(response, reverse("owner_job_detail", args=[new_job.pk]), fetch_redirect_response=False)

    def test_job_detail_renders(self):
        """GET /owner/jobs/<pk>/ renders vehicle info and status history section."""
        response = self.client.get(reverse("owner_job_detail", args=[self.job.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TC01 XYZ")
        self.assertContains(response, "Status Progression History")

    def test_job_edit_get(self):
        """GET /owner/jobs/<pk>/edit/ renders pre-populated form."""
        response = self.client.get(reverse("owner_job_edit", args=[self.job.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TC01 XYZ")

    def test_job_edit_post(self):
        """POST /owner/jobs/<pk>/edit/ updates job fields and redirects to detail."""
        response = self.client.post(reverse("owner_job_edit", args=[self.job.pk]), {
            "customer_name": "Updated Customer",
            "customer_phone": "",
            "license_plate": "TC01 XYZ",
            "vehicle_make": "Ford",
            "vehicle_model": "Focus",
            "description": "Updated description",
            "department": "mechanical",
            "status": "in_progress",
        })
        self.job.refresh_from_db()
        self.assertEqual(self.job.customer_name, "Updated Customer")
        self.assertEqual(self.job.status, "in_progress")
        self.assertRedirects(response, reverse("owner_job_detail", args=[self.job.pk]), fetch_redirect_response=False)

    def test_assign_technician_post(self):
        """POST /owner/jobs/<pk>/assign/ assigns technician and redirects to detail."""
        response = self.client.post(reverse("owner_job_assign", args=[self.job.pk]), {
            "technician": self.tech.pk,
        })
        self.job.refresh_from_db()
        self.assertEqual(self.job.assigned_technician, self.tech)
        self.assertRedirects(response, reverse("owner_job_detail", args=[self.job.pk]), fetch_redirect_response=False)

    def test_job_list_filter_by_status(self):
        """GET /owner/mechanical/?status=in_progress returns only in_progress jobs."""
        from .models import Job
        Job.objects.create(
            customer_name="Another",
            license_plate="IP01 BBB",
            vehicle_make="Vauxhall",
            vehicle_model="Astra",
            description="Oil service",
            status="in_progress",
            department=Department.MECHANICAL,
            created_by=self.owner,
        )
        response = self.client.get(reverse("owner_department_jobs", args=["mechanical"]) + "?status=in_progress")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "IP01 BBB")
        self.assertNotContains(response, "TC01 XYZ")



class TechFrontendTests(TestCase):
    """Tests for Step 12: Technician Frontend Views."""

    def setUp(self):
        from django.test import Client
        from .models import Job

        self.client = Client()

        # Owner
        self.owner = User.objects.create_user(username="bay_owner", password="OwnerPass123!")
        self.owner.profile.role = UserProfile.Role.OWNER
        self.owner.profile.save()

        # Tech A
        self.tech_a = User.objects.create_user(username="tech_a_bay", password="TechAPass123!")
        self.tech_a.profile.role = UserProfile.Role.TECHNICIAN
        self.tech_a.profile.department = Department.ELECTRONIC
        self.tech_a.profile.save()

        # Tech B
        self.tech_b = User.objects.create_user(username="tech_b_bay", password="TechBPass123!")
        self.tech_b.profile.role = UserProfile.Role.TECHNICIAN
        self.tech_b.profile.department = Department.ELECTRONIC
        self.tech_b.profile.save()

        # Job assigned to Tech A
        self.job_a = Job.objects.create(
            customer_name="Customer Tech A",
            license_plate="TA01 AAA",
            vehicle_make="Toyota",
            vehicle_model="Corolla",
            description="Brake pad replacement",
            department=Department.ELECTRONIC,
            assigned_technician=self.tech_a,
            created_by=self.owner,
        )

        # Job assigned to Tech B
        self.job_b = Job.objects.create(
            customer_name="Customer Tech B",
            license_plate="TB02 BBB",
            vehicle_make="Nissan",
            vehicle_model="Qashqai",
            description="Oil leak diagnosis",
            department=Department.ELECTRONIC,
            assigned_technician=self.tech_b,
            created_by=self.owner,
        )

        # Unassigned job
        self.job_unassigned = Job.objects.create(
            customer_name="Unassigned Customer",
            license_plate="UN03 CCC",
            vehicle_make="Vauxhall",
            vehicle_model="Corsa",
            description="Clutch issue",
            department=Department.ELECTRONIC,
            assigned_technician=None,
            created_by=self.owner,
        )

    def test_tech_bay_list_shows_only_assigned_jobs(self):
        """Technician bay view /tech/ displays only jobs assigned to the logged-in technician."""
        self.client.login(username="tech_a_bay", password="TechAPass123!")
        response = self.client.get(reverse("tech_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TA01 AAA")
        self.assertNotContains(response, "TB02 BBB")
        self.assertNotContains(response, "UN03 CCC")

    def test_tech_job_detail_renders(self):
        """GET /tech/jobs/<pk>/ renders vehicle details and status update form for assigned tech."""
        self.client.login(username="tech_a_bay", password="TechAPass123!")
        response = self.client.get(reverse("tech_job_detail", args=[self.job_a.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TA01 AAA")
        self.assertContains(response, "Post Status Update")
        self.assertContains(response, "Brake pad replacement")

    def test_tech_cannot_access_unassigned_job_detail(self):
        """GET /tech/jobs/<pk>/ returns 404 for an unassigned job."""
        self.client.login(username="tech_a_bay", password="TechAPass123!")
        response = self.client.get(reverse("tech_job_detail", args=[self.job_unassigned.pk]))
        self.assertEqual(response.status_code, 404)

    def test_tech_cannot_access_other_tech_job_detail(self):
        """GET /tech/jobs/<pk>/ returns 404 for a job assigned to another technician."""
        self.client.login(username="tech_a_bay", password="TechAPass123!")
        response = self.client.get(reverse("tech_job_detail", args=[self.job_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_tech_post_status_update(self):
        """POST /tech/jobs/<pk>/update/ creates StatusUpdate, syncs Job.status, and redirects."""
        from .models import Job, StatusUpdate
        self.client.login(username="tech_a_bay", password="TechAPass123!")
        response = self.client.post(reverse("tech_job_status_update", args=[self.job_a.pk]), {
            "status": "in_progress",
            "note": "Started removing front wheels.",
        })
        self.assertRedirects(response, reverse("tech_job_detail", args=[self.job_a.pk]), fetch_redirect_response=False)

        self.job_a.refresh_from_db()
        self.assertEqual(self.job_a.status, Job.Status.IN_PROGRESS)

        update = StatusUpdate.objects.filter(job=self.job_a).latest("created_at")
        self.assertEqual(update.status, Job.Status.IN_PROGRESS)
        self.assertEqual(update.note, "Started removing front wheels.")
        self.assertEqual(update.technician, self.tech_a)

    def test_tech_post_invalid_status(self):
        """POST /tech/jobs/<pk>/update/ with invalid status re-renders form with errors."""
        self.client.login(username="tech_a_bay", password="TechAPass123!")
        response = self.client.post(reverse("tech_job_status_update", args=[self.job_a.pk]), {
            "status": "invalid_status_value",
            "note": "Trying invalid status",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "status", "Select a valid choice. invalid_status_value is not one of the available choices.")

    def test_tech_cannot_post_status_update_on_unassigned_job(self):
        """POST /tech/jobs/<pk>/update/ returns 404 when technician attempts to update unassigned job."""
        self.client.login(username="tech_a_bay", password="TechAPass123!")
        response = self.client.post(reverse("tech_job_status_update", args=[self.job_unassigned.pk]), {
            "status": "in_progress",
            "note": "Unauthorized attempt",
        })
        self.assertEqual(response.status_code, 404)

    def test_owner_cannot_access_tech_detail(self):
        """Owner accessing /tech/jobs/<pk>/ receives 403 Forbidden."""
        self.client.login(username="bay_owner", password="OwnerPass123!")
        response = self.client.get(reverse("tech_job_detail", args=[self.job_a.pk]))
        self.assertEqual(response.status_code, 403)


class TwoDepartmentTests(TestCase):
    """Comprehensive tests for the Two-Department Architecture (Electronic & Mechanical)."""

    def setUp(self):
        from django.test import Client
        from .models import Job

        self.client = Client()

        # Owner
        self.owner = User.objects.create_user(username="dept_owner", password="OwnerPass123!")
        self.owner.profile.role = UserProfile.Role.OWNER
        self.owner.profile.save()

        # Electronic Technician
        self.elec_tech = User.objects.create_user(username="elec_tech_user", password="ElecPass123!")
        self.elec_tech.profile.role = UserProfile.Role.TECHNICIAN
        self.elec_tech.profile.department = Department.ELECTRONIC
        self.elec_tech.profile.save()

        # Mechanical Technician
        self.mech_tech = User.objects.create_user(username="mech_tech_user", password="MechPass123!")
        self.mech_tech.profile.role = UserProfile.Role.TECHNICIAN
        self.mech_tech.profile.department = Department.MECHANICAL
        self.mech_tech.profile.save()

        # Electronic Job
        self.elec_job = Job.objects.create(
            customer_name="Alice Electronic",
            license_plate="EL01 ECU",
            vehicle_make="BMW",
            vehicle_model="M3",
            description="ECU tuning & sensor wiring",
            department=Department.ELECTRONIC,
            assigned_technician=self.elec_tech,
            created_by=self.owner,
        )

        # Mechanical Job
        self.mech_job = Job.objects.create(
            customer_name="Bob Mechanical",
            license_plate="MC02 ENG",
            vehicle_make="Ford",
            vehicle_model="Mustang",
            description="V8 Engine rebuild",
            department=Department.MECHANICAL,
            assigned_technician=self.mech_tech,
            created_by=self.owner,
        )

    def test_owner_navigates_electronic_portal(self):
        """Owner visiting /owner/electronic/ sees only electronic jobs."""
        self.client.login(username="dept_owner", password="OwnerPass123!")
        response = self.client.get(reverse("owner_department_jobs", args=["electronic"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EL01 ECU")
        self.assertNotContains(response, "MC02 ENG")
        self.assertContains(response, "Electronic Repair")

    def test_owner_navigates_mechanical_portal(self):
        """Owner visiting /owner/mechanical/ sees only mechanical jobs."""
        self.client.login(username="dept_owner", password="OwnerPass123!")
        response = self.client.get(reverse("owner_department_jobs", args=["mechanical"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MC02 ENG")
        self.assertNotContains(response, "EL01 ECU")
        self.assertContains(response, "Mechanical Repair")

    def test_electronic_job_intake(self):
        """Creating a job in electronic portal automatically sets department to electronic."""
        from .models import Job
        self.client.login(username="dept_owner", password="OwnerPass123!")
        response = self.client.post(reverse("owner_department_job_create", args=["electronic"]), {
            "customer_name": "New Elec Customer",
            "license_plate": "EL99 NEW",
            "vehicle_make": "Tesla",
            "vehicle_model": "Model S",
            "description": "Battery management module diagnostic",
        })
        job = Job.objects.get(license_plate="EL99 NEW")
        self.assertEqual(job.department, Department.ELECTRONIC)
        self.assertRedirects(response, reverse("owner_job_detail", args=[job.pk]), fetch_redirect_response=False)

    def test_mechanical_job_intake(self):
        """Creating a job in mechanical portal automatically sets department to mechanical."""
        from .models import Job
        self.client.login(username="dept_owner", password="OwnerPass123!")
        response = self.client.post(reverse("owner_department_job_create", args=["mechanical"]), {
            "customer_name": "New Mech Customer",
            "license_plate": "MC99 NEW",
            "vehicle_make": "Toyota",
            "vehicle_model": "Hilux",
            "description": "Suspension replacement",
        })
        job = Job.objects.get(license_plate="MC99 NEW")
        self.assertEqual(job.department, Department.MECHANICAL)
        self.assertRedirects(response, reverse("owner_job_detail", args=[job.pk]), fetch_redirect_response=False)

    def test_assign_technician_cross_department_rejected(self):
        """Assigning a mechanical technician to an electronic job is rejected."""
        self.client.login(username="dept_owner", password="OwnerPass123!")
        response = self.client.post(reverse("owner_job_assign", args=[self.elec_job.pk]), {
            "technician": self.mech_tech.pk,
        })
        self.elec_job.refresh_from_db()
        self.assertNotEqual(self.elec_job.assigned_technician, self.mech_tech)

    def test_electronic_tech_cannot_see_mechanical_jobs(self):
        """Electronic tech bay view /tech/ displays only electronic jobs."""
        self.client.login(username="elec_tech_user", password="ElecPass123!")
        response = self.client.get(reverse("tech_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EL01 ECU")
        self.assertNotContains(response, "MC02 ENG")

    def test_electronic_tech_cannot_access_mechanical_job_detail(self):
        """Electronic tech receives 404 when querying a mechanical job detail."""
        self.client.login(username="elec_tech_user", password="ElecPass123!")
        response = self.client.get(reverse("tech_job_detail", args=[self.mech_job.pk]))
        self.assertEqual(response.status_code, 404)

    def test_mechanical_tech_cannot_access_electronic_job_detail(self):
        """Mechanical tech receives 404 when querying an electronic job detail."""
        self.client.login(username="mech_tech_user", password="MechPass123!")
        response = self.client.get(reverse("tech_job_detail", args=[self.elec_job.pk]))
        self.assertEqual(response.status_code, 404)


class OwnerSettingsAndTechManagementTests(TestCase):
    """Tests for Owner Settings, Profile updates, and Technician Management."""

    def setUp(self):
        from django.test import Client
        from .models import Job

        self.client = Client()

        # Owner
        self.owner = User.objects.create_user(
            username="settings_owner",
            password="OwnerPass123!",
            first_name="Moayed",
            email="owner@ecarspace.local",
        )
        self.owner.profile.role = UserProfile.Role.OWNER
        self.owner.profile.save()

        # Existing Technician
        self.tech = User.objects.create_user(
            username="existing_tech",
            password="TechPass123!",
        )
        self.tech.profile.role = UserProfile.Role.TECHNICIAN
        self.tech.profile.department = Department.ELECTRONIC
        self.tech.profile.save()

        # Job assigned to tech
        self.job = Job.objects.create(
            customer_name="Job Customer",
            license_plate="TECH-01",
            vehicle_make="Audi",
            vehicle_model="RS6",
            description="Dyno test",
            department=Department.ELECTRONIC,
            assigned_technician=self.tech,
            created_by=self.owner,
        )

    def test_owner_can_access_settings(self):
        """Owner accessing /owner/settings/ gets 200 OK with roster and profile forms."""
        self.client.login(username="settings_owner", password="OwnerPass123!")
        response = self.client.get(reverse("owner_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workshop Settings")
        self.assertContains(response, "existing_tech")

    def test_technician_cannot_access_settings(self):
        """Technician accessing /owner/settings/ receives 403 Forbidden."""
        self.client.login(username="existing_tech", password="TechPass123!")
        response = self.client.get(reverse("owner_settings"))
        self.assertEqual(response.status_code, 403)

    def test_owner_can_update_profile_info(self):
        """Owner can update their name, email, and phone number."""
        self.client.login(username="settings_owner", password="OwnerPass123!")
        response = self.client.post(reverse("owner_settings"), {
            "first_name": "Moayed Updated",
            "last_name": "Habbechi",
            "email": "updated@ecarspace.local",
            "phone_number": "07123456789",
        })
        self.assertRedirects(response, reverse("owner_settings"), fetch_redirect_response=False)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.first_name, "Moayed Updated")
        self.assertEqual(self.owner.last_name, "Habbechi")
        self.assertEqual(self.owner.profile.phone_number, "07123456789")

    def test_owner_can_change_password(self):
        """Owner can update their password and login with the new one."""
        self.client.login(username="settings_owner", password="OwnerPass123!")
        response = self.client.post(reverse("owner_password_change"), {
            "old_password": "OwnerPass123!",
            "new_password1": "NewOwnerPass999!",
            "new_password2": "NewOwnerPass999!",
        })
        self.assertRedirects(response, reverse("owner_settings"), fetch_redirect_response=False)
        self.client.logout()
        # Verify new password works
        self.assertTrue(self.client.login(username="settings_owner", password="NewOwnerPass999!"))

    def test_owner_can_add_electronic_technician(self):
        """Owner adds a new technician assigned to Electronic Repair."""
        self.client.login(username="settings_owner", password="OwnerPass123!")
        response = self.client.post(reverse("owner_technician_add"), {
            "username": "new_ecu_specialist",
            "email": "ecu@ecarspace.local",
            "phone_number": "07999888777",
            "department": Department.ELECTRONIC,
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
        })
        self.assertRedirects(response, reverse("owner_settings"), fetch_redirect_response=False)
        new_tech = User.objects.get(username="new_ecu_specialist")
        self.assertEqual(new_tech.profile.role, UserProfile.Role.TECHNICIAN)
        self.assertEqual(new_tech.profile.department, Department.ELECTRONIC)
        self.assertEqual(new_tech.profile.phone_number, "07999888777")

    def test_owner_can_add_mechanical_technician(self):
        """Owner adds a new technician assigned to Mechanical Repair."""
        self.client.login(username="settings_owner", password="OwnerPass123!")
        response = self.client.post(reverse("owner_technician_add"), {
            "username": "new_gearbox_specialist",
            "email": "gearbox@ecarspace.local",
            "phone_number": "07111222333",
            "department": Department.MECHANICAL,
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
        })
        self.assertRedirects(response, reverse("owner_settings"), fetch_redirect_response=False)
        new_tech = User.objects.get(username="new_gearbox_specialist")
        self.assertEqual(new_tech.profile.role, UserProfile.Role.TECHNICIAN)
        self.assertEqual(new_tech.profile.department, Department.MECHANICAL)

    def test_owner_can_delete_technician_and_unassign_jobs(self):
        """Deleting a technician unassigns their active jobs safely and removes the user."""
        self.client.login(username="settings_owner", password="OwnerPass123!")
        tech_id = self.tech.id
        response = self.client.post(reverse("owner_technician_delete", args=[tech_id]))
        self.assertRedirects(response, reverse("owner_settings"), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(id=tech_id).exists())
        self.job.refresh_from_db()
        self.assertIsNone(self.job.assigned_technician)

    def test_owner_can_access_edit_technician_page(self):
        """Owner accessing /owner/settings/technicians/<pk>/edit/ gets 200 with current tech data."""
        self.client.login(username="settings_owner", password="OwnerPass123!")
        response = self.client.get(reverse("owner_technician_edit", args=[self.tech.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.tech.username)
        self.assertContains(response, "Edit Technician Profile")

    def test_owner_can_edit_technician_name_and_contact(self):
        """Owner updates technician's first name, last name, and contact phone."""
        self.client.login(username="settings_owner", password="OwnerPass123!")
        response = self.client.post(reverse("owner_technician_edit", args=[self.tech.pk]), {
            "first_name": "Sam",
            "last_name": "Technician",
            "email": "sam.tech@ecarspace.local",
            "phone_number": "07555666777",
            "department": Department.ELECTRONIC,
        })
        self.assertRedirects(response, reverse("owner_settings"), fetch_redirect_response=False)
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.first_name, "Sam")
        self.assertEqual(self.tech.last_name, "Technician")
        self.assertEqual(self.tech.profile.phone_number, "07555666777")
        self.assertEqual(self.tech.profile.department, Department.ELECTRONIC)

    def test_department_change_unassigns_old_department_jobs(self):
        """Changing technician department transfers tech and unassigns active jobs from old department."""
        self.client.login(username="settings_owner", password="OwnerPass123!")
        self.assertEqual(self.job.assigned_technician, self.tech)
        self.assertEqual(self.tech.profile.department, Department.ELECTRONIC)

        response = self.client.post(reverse("owner_technician_edit", args=[self.tech.pk]), {
            "first_name": self.tech.first_name,
            "last_name": self.tech.last_name,
            "email": self.tech.email,
            "phone_number": "07555666777",
            "department": Department.MECHANICAL,
        })
        self.assertRedirects(response, reverse("owner_settings"), fetch_redirect_response=False)
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.profile.department, Department.MECHANICAL)
        # Job in electronic department must be safely unassigned
        self.job.refresh_from_db()
        self.assertIsNone(self.job.assigned_technician)

    def test_technician_cannot_access_technician_edit(self):
        """Technician accessing /owner/settings/technicians/<pk>/edit/ receives 403 Forbidden."""
        self.client.login(username="existing_tech", password="TechPass123!")
        response = self.client.get(reverse("owner_technician_edit", args=[self.tech.pk]))
        self.assertEqual(response.status_code, 403)










