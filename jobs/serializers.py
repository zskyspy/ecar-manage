from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Job, StatusUpdate, UserProfile




class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ("role", "phone_number", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "profile")


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Custom claims embedded in JWT
        token["username"] = user.username
        role = user.profile.role if hasattr(user, "profile") else "technician"
        token["role"] = role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        role = self.user.profile.role if hasattr(self.user, "profile") else "technician"
        data["username"] = self.user.username
        data["role"] = role
        return data


class JobSerializer(serializers.ModelSerializer):
    assigned_technician_name = serializers.CharField(
        source="assigned_technician.username",
        read_only=True,
        default=None,
        allow_null=True,
    )
    created_by_name = serializers.CharField(
        source="created_by.username",
        read_only=True,
        default=None,
        allow_null=True,
    )


    class Meta:
        model = Job
        fields = (
            "id",
            "customer_name",
            "customer_phone",
            "vehicle_make",
            "vehicle_model",
            "vehicle_year",
            "license_plate",
            "vin",
            "description",
            "status",
            "assigned_technician",
            "assigned_technician_name",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_by",
            "created_by_name",
            "assigned_technician_name",
            "created_at",
            "updated_at",
        )


class JobAssignSerializer(serializers.Serializer):
    technician_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_technician_id(self, value):
        if value is None:
            return None
        try:
            user = User.objects.select_related("profile").get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(f"User with id {value} does not exist.")

        if not hasattr(user, "profile") or not user.profile.is_technician:
            raise serializers.ValidationError(
                f"User '{user.username}' does not have the technician role."
            )
        return value


class StatusUpdateSerializer(serializers.ModelSerializer):
    technician_name = serializers.CharField(
        source="technician.username",
        read_only=True,
        default=None,
        allow_null=True,
    )

    class Meta:
        model = StatusUpdate
        fields = (
            "id",
            "job",
            "status",
            "note",
            "technician",
            "technician_name",
            "created_at",
        )
        read_only_fields = ("id", "job", "technician", "technician_name", "created_at")



