from django.db import connection
from django.http import HttpResponse, JsonResponse
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .filters import JobFilter
from .models import Job
from .permissions import IsOwner, IsTechnician
from .serializers import (
    CustomTokenObtainPairSerializer,
    JobSerializer,
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
    queryset = Job.objects.all().select_related("assigned_technician", "created_by")
    serializer_class = JobSerializer
    filterset_class = JobFilter
    search_fields = ["customer_name", "license_plate", "vehicle_make", "vehicle_model", "vin"]
    ordering_fields = ["created_at", "updated_at", "status"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()


