from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import IsGameAdmin
from .serializers import RegisterSerializer, UserProfileSerializer, CustomTokenObtainPairSerializer
from drf_spectacular.utils import extend_schema, OpenApiResponse

User = get_user_model()


class AccountViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()

    def get_permissions(self):
        if self.action == 'register':
            permission_classes = [permissions.AllowAny]
        elif self.action in ['kick_user', 'reset_coins']:
            permission_classes = [IsGameAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'register':
            return RegisterSerializer
        if self.action in ['kick_user', 'reset_coins']:
            return None
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
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def kick_user(self, pk=None):
        user = get_object_or_404(User, pk=pk)
        user.delete()
        return Response({'message': 'User kicked successfully'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def reset_coins(self, pk=None):
        user = get_object_or_404(User, pk=pk)
        user.coin = 0
        user.save()
        return Response({'message': 'User coins reset to 0'}, status=status.HTTP_200_OK)

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
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
