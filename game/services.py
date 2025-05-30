import random
from django.core.cache import cache
from django.db.models import F

from accounts.models import User
from .models import Game, GuessHistory, GameHistory


class GameService:
    # Cache timeouts in seconds
    GAME_CACHE_TIMEOUT = 60 * 15  # 15 minutes
    ACTIVE_GAMES_CACHE_TIMEOUT = 60 * 10  # 10 minutes

    @staticmethod
    def _get_game_cache_key(game_id):
        """Generate cache key for game object"""
        return f"game:{game_id}"

    @staticmethod
    def _get_user_active_game_cache_key(user_id):
        """Generate cache key for user's active game"""
        return f"user:active_game:{user_id}"

    @staticmethod
    def _get_user_active_games_check_key(user_id):
        """Generate cache key for user's active games check"""
        return f"user:has_active_games:{user_id}"

    @staticmethod
    def _cache_game(game):
        cache_key = GameService._get_game_cache_key(game.id)
        cache.set(cache_key, game, GameService.GAME_CACHE_TIMEOUT)

    @staticmethod
    def _get_cached_game(game_id):
        """Retrieve cached game object"""
        cache_key = GameService._get_game_cache_key(game_id)
        return cache.get(cache_key)

    @staticmethod
    def _invalidate_game_cache(game_id):
        """Remove game from cache"""
        cache_key = GameService._get_game_cache_key(game_id)
        cache.delete(cache_key)

    @staticmethod
    def invalidate_user_game_caches(user_id):
        """Invalidate all user-related game caches"""
        user_active_key = GameService._get_user_active_game_cache_key(user_id)
        user_check_key = GameService._get_user_active_games_check_key(user_id)
        cache.delete_many([user_active_key, user_check_key])

    @staticmethod
    def get_current_user_game(user):
        """Get user's current active game with caching"""
        cache_key = GameService._get_user_active_game_cache_key(user.id)

        # Try to get from cache first
        cached_game_id = cache.get(cache_key)
        if cached_game_id:
            # Try to get the full game object from cache
            game = GameService._get_cached_game(cached_game_id)
            if game:
                # Verify the game is still active and user is still a player
                if game.status == 2 and game.players.filter(user=user).exists():
                    return game
                else:
                    # Game state changed, invalidate cache
                    GameService._invalidate_game_cache(cached_game_id)
                    cache.delete(cache_key)

        # Cache miss or invalid - fetch from database
        game = Game.objects.filter(players__user=user, status=2).first()

        if game:
            # Cache both the game object and the user's active game reference
            GameService._cache_game(game)
            cache.set(cache_key, game.id, GameService.ACTIVE_GAMES_CACHE_TIMEOUT)
        else:
            # Cache negative result to prevent repeated DB queries
            cache.set(cache_key, None, 60)  # Short timeout for negative cache

        return game

    @staticmethod
    def check_active_games(user):
        """Check if user has active games with caching"""
        cache_key = GameService._get_user_active_games_check_key(user.id)

        # Try cache first
        result = cache.get(cache_key)
        if result is not None:
            return result

        # Cache miss - check database
        has_active = Game.objects.filter(creator=user, status__in=[1, 2]).exists()

        # Cache the result
        cache.set(cache_key, has_active, GameService.ACTIVE_GAMES_CACHE_TIMEOUT)

        return has_active

    @staticmethod
    def process_guess(user, letter):
        """Process letter guess with cache management"""
        game = GameService.get_current_user_game(user)
        if not game:
            return {'success': False, 'message': 'No active game', 'game': None}

        result = game.guess_letter(user, letter)

        if result['success']:
            # Update game in cache after successful guess
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

            # If game completed, invalidate caches
            if game.status == 3:
                GameService._invalidate_game_cache(game.pk)
                # Invalidate cache for all players in the game
                for player in game.players.all():
                    GameService.invalidate_user_game_caches(player.user.id)

        return {**result, 'game': game}

    @staticmethod
    def process_word_guess(user, guessed_word):
        """Process word guess with cache management"""
        game = GameService.get_current_user_game(user)
        if not game or game.status != 2:
            return {'success': False, 'message': 'Game is not active', 'game': None}

        player = game.players.get(user=user)

        if guessed_word.lower() == game.word.lower():
            # Correct guess - player wins
            game.winner = user
            game.masked_word = game.word.lower()
            game.save()

            GameHistory.objects.create(
                game=game,
                player=player.user,
                score=100,
                result='win',
                guessed_word=guessed_word
            )

            game.end_game()

            # Invalidate caches after game ends
            GameService._invalidate_game_cache(game.pk)
            for p in game.players.all():
                GameService.invalidate_user_game_caches(p.user.id)

            return {
                'success': True,
                'message': 'Correct! You win the game',
                'game': game
            }
        else:
            # Incorrect guess - player loses
            game.status = 3
            opponent = game.players.exclude(user=user).first()
            if opponent:
                game.winner = opponent.user
            game.masked_word = game.word.lower()
            game.save()

            GameHistory.objects.create(
                game=game,
                player=player.user,
                score=-50,
                result='lose',
                guessed_word=guessed_word
            )

            game.end_game()

            # Invalidate caches after game ends
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
        """Reveal letter with cache management"""
        game = GameService.get_current_user_game(user)
        if not game or game.status != 2:
            return {'success': False, 'message': 'Game not active'}

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
    def leaderboard(num):
        top_players = (
            User.objects
            .values('username')
            .annotate(total_score=F('xp'))
            .order_by('-total_score')[:num]
        )
        return top_players
