import random
from .models import Game, Player, GuessHistory, GameHistory


class GameService:
    @staticmethod
    def get_current_user_game(user):
        """Get the current active game for a user"""
        return Game.objects.filter(players__user=user, status=2).first()

    @staticmethod
    def check_active_games(user):
        """Check if user has active or waiting games"""
        return Game.objects.filter(creator=user, status__in=[1, 2]).exists()

    @staticmethod
    def process_guess(user, letter):
        """Process a letter guess"""
        game = GameService.get_current_user_game(user)
        if not game:
            return {'success': False, 'message': 'No active game', 'game': None}

        result = game.guess_letter(user, letter)

        if result['success']:
            player = game.players.get(user=user)
            GuessHistory.objects.create(
                player=player,
                game=game,
                letter=letter,
                is_correct=result['points'] > 0,
                points=result['points']
            )

        return {**result, 'game': game}

    @staticmethod
    def process_word_guess(user, guessed_word):
        game = GameService.get_current_user_game(user)

        if not game or game.status != 2:
            return {'success': False, 'message': 'Game is not active', 'game': None}

        player = game.players.get(user=user)

        if guessed_word.lower() == game.word.lower():
            game.winner = user
            game.masked_word = game.word.lower()
            game.save()

            GameHistory.objects.create(
                game=game,
                player=player,
                score=100,
                result='win',
                guessed_word=guessed_word
            )

            game.end_game()
            return {
                'success': True,
                'message': 'Correct! You win the game',
                'game': game
            }
        else:
            # Incorrect guess
            game.status = 3
            opponent = game.players.exclude(user=user).first()
            if opponent:
                game.winner = opponent.user
            game.masked_word = game.word.lower()
            game.save()

            GameHistory.objects.create(
                game=game,
                player=player,
                score=-50,
                result='lose',
                guessed_word=guessed_word
            )

            game.end_game()
            return {
                'success': False,
                'message': 'Incorrect guess. You lost the game',
                'game': game
            }

    @staticmethod
    def reveal_letter(user, reveal_cost=30):
        """Reveal a random hidden letter"""
        game = GameService.get_current_user_game(user)

        if not game or game.status != 2:
            return {'success': False, 'message': 'Game not active'}

        try:
            player = game.players.get(user=user)
        except Player.DoesNotExist:
            return {'success': False, 'message': 'Not in game'}

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

        return {
            'success': True,
            'message': f"Letter revealed at position {pos + 1}",
            'masked_word': game.masked_word,
            'coins_spent': reveal_cost,
            'remaining_coins': user.coin
        }