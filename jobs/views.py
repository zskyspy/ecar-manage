from django.db import connection
from django.http import HttpResponse, JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

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
    return JsonResponse({"status": "ok", "app": "GarageFlow", "database": "connected"})


def home(request):
    return HttpResponse("GarageFlow is running.")


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




