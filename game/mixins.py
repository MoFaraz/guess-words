from .models import Game


class GameMixin:
    """Mixin for common game-related functionality"""

    def check_active_games(self):
        """Check and update expired games"""
        active_games = Game.objects.filter(status=2)
        for game in active_games:
            if game.is_expired():
                game.end_game()


class ThrottleMixin:
    """Mixin for dynamic throttle selection based on action"""

    def get_throttles(self):
        """Select throttle class based on action"""
        # This method is overridden in specific viewsets
        return super().get_throttles()