from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .account_swagger import AccountSwaggerDocs, AuthSwaggerDocs
from .models import User
from .permissions import IsGameAdmin
from .serializers import RegisterSerializer, UserProfileSerializer, CustomTokenObtainPairSerializer


class AccountViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()

    def get_permissions(self):
        if self.action == 'register':
            permission_classes = [permissions.AllowAny]
        elif self.action in ['kick_user', 'reset_coins', 'make_admin']:
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

    @AccountSwaggerDocs.register
    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            UserProfileSerializer(user).data,
            status=status.HTTP_201_CREATED
        )

    @AccountSwaggerDocs.profile
    @action(detail=False, methods=['get'])
    def profile(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @AccountSwaggerDocs.kick_user
    @action(detail=True, methods=['post'])
    def kick_user(self, pk=None):
        user = get_object_or_404(User, pk=pk)
        user.delete()
        return Response({'message': 'User kicked successfully'}, status=status.HTTP_200_OK)

    @AccountSwaggerDocs.reset_coins
    @action(detail=True, methods=['post'])
    def reset_coins(self, pk=None):
        user = get_object_or_404(User, pk=pk)
        user.coin = 0
        user.save()
        return Response({'message': 'User coins reset to 0'}, status=status.HTTP_200_OK)

    @AccountSwaggerDocs.update_profile
    @profile.mapping.patch
    def update_profile(self, request):
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


    @AccountSwaggerDocs.make_admin
    @action(detail=True, methods=['post'])
    def make_admin(self, pk):
        user = get_object_or_404(User, pk=pk)
        if user.role == 'admin':
            return Response({'detail': 'User is already admin.'}, status=status.HTTP_400_BAD_REQUEST)

        user.role = 'admin'
        user.save()
        return Response({'detail': f'User {user.username} is now an admin.'}, status=status.HTTP_200_OK)


@AuthSwaggerDocs.token_obtain_pair
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
