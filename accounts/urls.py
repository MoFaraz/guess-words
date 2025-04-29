from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import AccountViewSet, CustomTokenObtainPairView

router = DefaultRouter()
router.register('', AccountViewSet, basename='accounts')

urlpatterns = [
    # JWT token endpoints
    # path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
] + router.urls
