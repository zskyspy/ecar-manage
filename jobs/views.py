from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .mixins import OwnerRequiredMixin, TechnicianRequiredMixin

from .filters import JobFilter
from .models import Job
from .permissions import IsOwner, IsTechnician
from .serializers import (
    CustomTokenObtainPairSerializer,
    JobAssignSerializer,
    JobSerializer,
    StatusUpdateSerializer,
    UserSerializer,
)




def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1;")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "app": "ECAR Space", "database": "connected"})


def home(request):
    return HttpResponse("ECAR Space is running.")


class CustomTokenObtainPairView(TokenObtainPairView):
    permission_classes = (AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer


class CurrentUserView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OwnerOnlyTestView(APIView):
    permission_classes = (IsAuthenticated, IsOwner)

    def get(self, request):
        return Response(
            {"message": f"Hello Owner {request.user.username}, access granted.", "role": request.user.profile.role},
            status=status.HTTP_200_OK,
        )


class TechnicianOnlyTestView(APIView):
    permission_classes = (IsAuthenticated, IsTechnician)

    def get(self, request):
        return Response(
            {"message": f"Hello Technician {request.user.username}, access granted.", "role": request.user.profile.role},
            status=status.HTTP_200_OK,
        )


class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    filterset_class = JobFilter
    search_fields = ["customer_name", "license_plate", "vehicle_make", "vehicle_model", "vin"]
    ordering_fields = ["created_at", "updated_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Job.objects.none()

        # Owners and superusers can view all jobs
        if getattr(user, "is_superuser", False) or (
            hasattr(user, "profile") and user.profile.is_owner
        ):
            return Job.objects.all().select_related("assigned_technician", "created_by")

        # Technicians can only view jobs assigned to them
        if hasattr(user, "profile") and user.profile.is_technician:
            return Job.objects.filter(assigned_technician=user).select_related(
                "assigned_technician", "created_by"
            )

        return Job.objects.none()


    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsOwner],
    )
    def assign(self, request, pk=None):
        job = self.get_object()
        serializer = JobAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tech_id = serializer.validated_data.get("technician_id")
        if tech_id is None:
            job.assigned_technician = None
        else:
            job.assigned_technician_id = tech_id
        job.save()
        return Response(JobSerializer(job).data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="status-updates",
        permission_classes=[IsAuthenticated],
    )
    def status_updates(self, request, pk=None):
        job = self.get_object()

        if request.method == "GET":
            updates = job.status_updates.all().select_related("technician")
            serializer = StatusUpdateSerializer(updates, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # POST: Must be the assigned technician
        if job.assigned_technician != request.user:
            return Response(
                {"detail": "Only the assigned technician can post status updates for this job."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = StatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status_update = serializer.save(job=job, technician=request.user)

        # Update parent Job status
        job.status = status_update.status
        job.save(update_fields=["status", "updated_at"])

        return Response(StatusUpdateSerializer(status_update).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Template-based frontend views (Step 10)
# ---------------------------------------------------------------------------

class DashboardRedirectView(LoginRequiredMixin, View):
    """
    After login, redirect the user to the role-appropriate dashboard.
    Unauthenticated users are sent to /login/ by LoginRequiredMixin.
    """

    def get(self, request, *args, **kwargs):
        user = request.user
        if hasattr(user, "profile") and user.profile.is_technician:
            return redirect("tech_dashboard")
        # Owners, superusers, and any other authenticated users go to owner dashboard
        return redirect("owner_dashboard")


class OwnerDashboardView(OwnerRequiredMixin, View):
    """Owner portal home: redirect straight to the job list."""

    def get(self, request):
        return redirect("owner_job_list")


class TechnicianDashboardView(TechnicianRequiredMixin, TemplateView):
    """Technician bay view: lists only jobs assigned to the requesting technician."""

    template_name = "jobs/tech_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["jobs"] = (
            Job.objects.filter(assigned_technician=self.request.user)
            .prefetch_related("status_updates")
            .order_by("-created_at")
        )
        return ctx


# ---------------------------------------------------------------------------
# Step 11: Owner Frontend CRUD Views
# ---------------------------------------------------------------------------

class OwnerJobListView(OwnerRequiredMixin, View):
    """Filterable list of all jobs in the workshop."""

    template_name = "jobs/job_list.html"

    STATUS_BADGE = {
        Job.Status.PENDING: "info",
        Job.Status.IN_PROGRESS: "warning",
        Job.Status.WAITING_PARTS: "danger",
        Job.Status.COMPLETED: "success",
        Job.Status.CANCELLED: "secondary",
    }

    def get(self, request):
        from django.contrib.auth.models import User as DjangoUser
        from .models import UserProfile

        qs = (
            Job.objects.all()
            .select_related("assigned_technician", "created_by")
            .order_by("-created_at")
        )

        # --- filters ---
        status_filter = request.GET.get("status", "")
        tech_filter = request.GET.get("technician", "")
        plate_filter = request.GET.get("plate", "").strip()

        if status_filter:
            qs = qs.filter(status=status_filter)
        if tech_filter == "unassigned":
            qs = qs.filter(assigned_technician__isnull=True)
        elif tech_filter:
            qs = qs.filter(assigned_technician__username=tech_filter)
        if plate_filter:
            qs = qs.filter(license_plate__icontains=plate_filter)

        tech_ids = UserProfile.objects.filter(
            role=UserProfile.Role.TECHNICIAN
        ).values_list("user_id", flat=True)
        technicians = DjangoUser.objects.filter(id__in=tech_ids).order_by("username")

        return render(request, self.template_name, {
            "jobs": qs,
            "total": Job.objects.count(),
            "in_progress": Job.objects.filter(status=Job.Status.IN_PROGRESS).count(),
            "waiting_parts": Job.objects.filter(status=Job.Status.WAITING_PARTS).count(),
            "completed": Job.objects.filter(status=Job.Status.COMPLETED).count(),
            "status_choices": Job.Status.choices,
            "technicians": technicians,
            "current_status": status_filter,
            "current_tech": tech_filter,
            "current_plate": plate_filter,
        })


class OwnerJobCreateView(OwnerRequiredMixin, View):
    """Create a new repair job."""

    template_name = "jobs/job_create.html"

    def get(self, request):
        from .forms import JobCreateForm
        return render(request, self.template_name, {"form": JobCreateForm()})

    def post(self, request):
        from .forms import JobCreateForm
        form = JobCreateForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.created_by = request.user
            job.save()
            messages.success(request, f"Job #{job.id} created successfully.")
            return redirect("owner_job_detail", pk=job.pk)
        return render(request, self.template_name, {"form": form})


class OwnerJobDetailView(OwnerRequiredMixin, View):
    """Job detail page: info, assign technician form, status history timeline."""

    template_name = "jobs/job_detail.html"

    def get(self, request, pk):
        from .forms import AssignTechnicianForm
        job = get_object_or_404(
            Job.objects.select_related("assigned_technician", "created_by")
            .prefetch_related("status_updates__technician"),
            pk=pk,
        )
        assign_form = AssignTechnicianForm(
            initial={"technician": job.assigned_technician}
        )
        return render(request, self.template_name, {
            "job": job,
            "assign_form": assign_form,
        })


class OwnerJobEditView(OwnerRequiredMixin, View):
    """Edit job fields (customer info, vehicle info, description, status)."""

    template_name = "jobs/job_edit.html"

    def get(self, request, pk):
        from .forms import JobEditForm
        job = get_object_or_404(Job, pk=pk)
        return render(request, self.template_name, {
            "form": JobEditForm(instance=job),
            "job": job,
        })

    def post(self, request, pk):
        from .forms import JobEditForm
        job = get_object_or_404(Job, pk=pk)
        form = JobEditForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, f"Job #{job.id} updated successfully.")
            return redirect("owner_job_detail", pk=job.pk)
        return render(request, self.template_name, {"form": form, "job": job})


class OwnerAssignTechnicianView(OwnerRequiredMixin, View):
    """POST-only: assign or unassign a technician to/from a job."""

    def post(self, request, pk):
        from .forms import AssignTechnicianForm
        job = get_object_or_404(Job, pk=pk)
        form = AssignTechnicianForm(request.POST)
        if form.is_valid():
            tech = form.cleaned_data["technician"]
            job.assigned_technician = tech
            job.save(update_fields=["assigned_technician", "updated_at"])
            name = tech.username if tech else "None"
            messages.success(request, f"Technician updated to: {name}.")
        else:
            messages.error(request, "Invalid technician selection.")
        return redirect("owner_job_detail", pk=job.pk)


# ---------------------------------------------------------------------------
# Step 12: Technician Frontend Views
# ---------------------------------------------------------------------------

class TechJobDetailView(TechnicianRequiredMixin, View):
    """Job detail page for assigned technician: view details + post status updates."""

    template_name = "jobs/tech_job_detail.html"

    def get(self, request, pk):
        from .forms import StatusUpdateForm
        # Ensure the technician can ONLY retrieve a job assigned to them
        job = get_object_or_404(
            Job.objects.filter(assigned_technician=request.user)
            .select_related("assigned_technician", "created_by")
            .prefetch_related("status_updates__technician"),
            pk=pk,
        )
        form = StatusUpdateForm(initial={"status": job.status})
        return render(request, self.template_name, {
            "job": job,
            "form": form,
        })


class TechPostStatusUpdateView(TechnicianRequiredMixin, View):
    """POST-only: Technician posts a new status update and syncs parent Job.status."""

    def post(self, request, pk):
        from .forms import StatusUpdateForm
        from .models import StatusUpdate
        # Strictly verify job is assigned to requesting technician
        job = get_object_or_404(
            Job.objects.filter(assigned_technician=request.user),
            pk=pk,
        )
        form = StatusUpdateForm(request.POST)
        if form.is_valid():
            new_status = form.cleaned_data["status"]
            note = form.cleaned_data.get("note", "")

            # Create status update record
            StatusUpdate.objects.create(
                job=job,
                status=new_status,
                note=note,
                technician=request.user,
            )

            # Sync parent job
            job.status = new_status
            job.save(update_fields=["status", "updated_at"])

            messages.success(request, f"Status updated to {job.get_status_display()}.")
            return redirect("tech_job_detail", pk=job.pk)

        # If form is invalid, re-render detail template
        return render(request, "jobs/tech_job_detail.html", {
            "job": job,
            "form": form,
        })







