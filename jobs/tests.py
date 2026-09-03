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
        self.assigned_tech.profile.save()

        # Create Unassigned Technician
        self.unassigned_tech = User.objects.create_user(
            username="unassigned_tech",
            password="TechPassword123!",
        )
        self.unassigned_tech.profile.role = UserProfile.Role.TECHNICIAN
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
        self.tech_a.profile.save()

        # Create Technician B
        self.tech_b = User.objects.create_user(
            username="tech_b",
            password="TechPassword123!",
        )
        self.tech_b.profile.role = UserProfile.Role.TECHNICIAN
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




