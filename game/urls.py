from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'games', views.GameViewSet, basename='game')
router.register(r'wordbanks', views.WordBankViewSet, basename='word')
router.register('history', views.GameHistoryViewSet, basename='history')
router.register('leaderboard', views.LeaderboardViewSet, basename='leaderboard')

urlpatterns = router.urls
