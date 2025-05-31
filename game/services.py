import random
from django.core.cache import cache
from django.db.models import F
from rest_framework.generics import get_object_or_404

from accounts.models import User
from .models import Game, GuessHistory, GameHistory, Player


class GameService:
    GAME_CACHE_TIMEOUT = 60 * 15
    ACTIVE_GAMES_CACHE_TIMEOUT = 60 * 10

    @staticmethod
    def _get_game_cache_key(game_id):
        return f"game:{game_id}"

    @staticmethod
    def _get_user_active_game_cache_key(user_id):
        return f"user:active_game:{user_id}"

    @staticmethod
    def _get_user_active_games_check_key(user_id):
        return f"user:has_active_games:{user_id}"

    @staticmethod
    def _cache_game(game):
        cache_key = GameService._get_game_cache_key(game.pk)
        cache.set(cache_key, game, GameService.GAME_CACHE_TIMEOUT)

    @staticmethod
    def _get_cached_game(game_id):
        cache_key = GameService._get_game_cache_key(game_id)
        return cache.get(cache_key)

    @staticmethod
    def _invalidate_game_cache(game_id):
        cache_key = GameService._get_game_cache_key(game_id)
        cache.delete(cache_key)

    @staticmethod
    def invalidate_user_game_caches(user_id):
        user_active_key = GameService._get_user_active_game_cache_key(user_id)
        user_check_key = GameService._get_user_active_games_check_key(user_id)
        cache.delete_many([user_active_key, user_check_key])

    @staticmethod
    def get_current_user_game(user):
        cache_key = GameService._get_user_active_game_cache_key(user.id)

        cached_game_id = cache.get(cache_key)
        if cached_game_id:
            game = GameService._get_cached_game(cached_game_id)
            if game:
                if game.status == 2 and game.players.filter(user=user).exists():
                    return game
                else:
                    GameService._invalidate_game_cache(cached_game_id)
                    cache.delete(cache_key)

        game = get_object_or_404(Game, players__user=user, status=2)

        if game:
            GameService._cache_game(game)
            cache.set(cache_key, game.pk, GameService.ACTIVE_GAMES_CACHE_TIMEOUT)
        else:
            cache.set(cache_key, None, 60)  # Short timeout for negative cache

        return game

    @staticmethod
    def check_active_games(user):
        cache_key = GameService._get_user_active_games_check_key(user.id)

        result = cache.get(cache_key)
        if result is not None:
            return result

        has_active = Game.objects.filter(creator=user, status__in=[1, 2]).exists()

        cache.set(cache_key, has_active, GameService.ACTIVE_GAMES_CACHE_TIMEOUT)

        return has_active

    @staticmethod
    def process_guess(user, letter):
        game = GameService.get_current_user_game(user)
        if not game:
            return {'success': False, 'message': 'No active game', 'game': None}

        result = game.guess_letter(user, letter)

        if result['success']:
            GameService._cache_game(game)

            # Create guess history
            player = game.players.get(user=user)
            GuessHistory.objects.create(
                player=player.user,
                game=game,
                letter=letter,
                is_correct=result['points'] > 0,
                points=result['points']
            )

            if game.status == 3:
                GameService._invalidate_game_cache(game.pk)
                for player in game.players.all():
                    GameService.invalidate_user_game_caches(player.user.id)

        return {**result, 'game': game}

    @staticmethod
    def process_word_guess(user, guessed_word):
        game = GameService.get_current_user_game(user)
        if not game or game.status != 2:
            return {'success': False, 'message': 'Game is not active', 'game': None}

        try:
            player = game.players.get(user=user)
        except Player.DoesNotExist:
            return {'success': False, 'message': 'You are not part of this game', 'game': None}

        if guessed_word.lower() == game.word.lower():
            game.winner = user
            game.masked_word = game.word.lower()
            game.status = 3
            game.save()

            player.score += 200
            player.save()

            game.end_game()

            GameService._invalidate_game_cache(game.pk)
            for p in game.players.all():
                GameService.invalidate_user_game_caches(p.user.id)

            return {
                'success': True,
                'message': 'Correct! You win the game',
                'game': game
            }

        else:
            game.status = 3
            game.masked_word = game.word.lower()

            opponent = game.players.exclude(user=user).first()
            if opponent:
                game.winner = opponent.user

            game.save()

            player.score -= 200
            player.save()

            game.end_game()

            GameService._invalidate_game_cache(game.pk)
            for p in game.players.all():
                GameService.invalidate_user_game_caches(p.user.id)

            return {
                'success': False,
                'message': 'Incorrect guess. You lost the game',
                'game': game
            }

    @staticmethod
    def reveal_letter(user, reveal_cost=30):
        game = GameService.get_current_user_game(user)
        if not game or game.status != 2:
            return {'success': False, 'message': 'Game not active'}

        if not game.current_turn == user:
            return {'success': False, 'message': 'Not Your Turn'}

        if '_' not in game.masked_word:
            return {'success': False, 'message': 'No hidden letters to reveal'}

        if not user.deduct_coins(reveal_cost):
            return {'success': False, 'message': 'Not enough coins'}

        hidden_positions = [i for i, char in enumerate(game.masked_word) if char == '_']
        pos = random.choice(hidden_positions)
        new_masked = list(game.masked_word)
        new_masked[pos] = game.word[pos]
        game.masked_word = ''.join(new_masked)
        game.save()

        # Update game in cache
        GameService._cache_game(game)

        return {
            'success': True,
            'message': f"Letter revealed at position {pos + 1}",
            'masked_word': game.masked_word,
            'coins_spent': reveal_cost,
            'remaining_coins': user.coin
        }

    @staticmethod
    def invalidate_all_game_caches(game_id):
        """Utility method to invalidate all caches related to a game"""
        try:
            game = Game.objects.get(pk=game_id)
            GameService._invalidate_game_cache(game_id)

            # Invalidate cache for all players
            for player in game.players.all():
                GameService.invalidate_user_game_caches(player.user.pk)

        except Game.DoesNotExist:
            # Game doesn't exist, just invalidate the game cache
            GameService._invalidate_game_cache(game_id)

    @staticmethod
    def cache_active_game(game):
        """Utility method to manually cache a game (useful after game creation/updates)"""
        if game and game.status in [1, 2]:  # Only cache waiting or active games
            GameService._cache_game(game)

            # Cache user references for all players
            for player in game.players.all():
                if game.status == 2:  # Only cache active game reference for active games
                    user_cache_key = GameService._get_user_active_game_cache_key(player.user.id)
                    cache.set(user_cache_key, game.pk, GameService.ACTIVE_GAMES_CACHE_TIMEOUT)

    @staticmethod
    def leaderboard():
        top_players = (
            User.objects
            .values('username')
            .annotate(total_score=F('xp'))
            .order_by('-total_score')
        )
        return top_players
