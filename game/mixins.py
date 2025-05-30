from .models import Game


class GameMixin:
    def check_active_games(self):
        active_games = Game.objects.filter(status=2)
        for game in active_games:
            if game.is_expired():
                game.end_game()


class ThrottleMixin:
    def get_throttles(self):
        return super().get_throttles()