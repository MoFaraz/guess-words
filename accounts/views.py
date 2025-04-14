from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer, UserProfileSerializer
from drf_spectacular.utils import extend_schema, OpenApiResponse

User = get_user_model()


class AccountViewSet(viewsets.GenericViewSet):
    """
    ViewSet for user account operations including registration and profile management.
    """
    queryset = User.objects.all()

    def get_permissions(self):
        """
        Set permissions based on the action being performed.
        - Register: open to anyone
        - Profile access: authenticated users only
        """
        if self.action == 'register':
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        """Return appropriate serializer class based on the action"""
        if self.action == 'register':
            return RegisterSerializer
        return UserProfileSerializer

    @extend_schema(
        summary="Register a new user",
        description="Create a new user account with username, email, and password",
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(description="User successfully created", response=UserProfileSerializer),
            400: OpenApiResponse(description="Bad request, validation error")
        }
    )
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Create a new user account"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            UserProfileSerializer(user).data,
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Get user profile",
        description="Retrieve the authenticated user's profile information",
        responses={
            200: UserProfileSerializer,
            401: OpenApiResponse(description="Unauthorized")
        }
    )
    @action(detail=False, methods=['get'])
    def profile(self, request):
        """Get the current user's profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @extend_schema(
        summary="Update user profile",
        description="Update the authenticated user's profile information",
        request=UserProfileSerializer,
        responses={
            200: UserProfileSerializer,
            400: OpenApiResponse(description="Bad request, validation error"),
            401: OpenApiResponse(description="Unauthorized")
        }
    )
    @profile.mapping.patch
    def update_profile(self, request):
        """Update the current user's profile"""
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)