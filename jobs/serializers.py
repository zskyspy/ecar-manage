from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import UserProfile


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
