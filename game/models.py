import random
from django.utils import timezone

from datetime import timedelta

from django.db import models

from accounts.models import User


class WordBank(models.Model):
    DIFFICULTY_CHOICES = [
        (1, 'Easy'),
        (2, 'Medium'),
        (3, 'Hard'),
    ]

    word = models.CharField(max_length=30)
    difficulty = models.IntegerField(choices=DIFFICULTY_CHOICES, default=1)

    class Meta:
        indexes = [
            models.Index(fields=['difficulty']),
        ]

    def __str__(self):
        return f"{self.word} ({self.difficulty})"

    @classmethod
    def get_random_word(cls, difficulty):
        words = cls.objects.filter(difficulty=difficulty).values_list('word', flat=True)
        if not words.exists():
            return None
        return random.choice(list(words))


class Game(models.Model):
    DIFFICULTY_CHOICES = [
        (1, 'Easy'),
        (2, 'Medium'),
        (3, 'Hard'),
    ]

    STATUS_CHOICES = [
        (1, 'Waiting For Players'),
        (2, 'Active'),
        (3, 'Completed'),
    ]

    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    difficulty = models.IntegerField(choices=DIFFICULTY_CHOICES, default=1)
    word = models.CharField(max_length=30)
    masked_word = models.CharField(max_length=20, null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.IntegerField(choices=STATUS_CHOICES, default=1)
    current_turn = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='games_turn')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.creator} game with difficulty ({self.difficulty})"

    def save(self, *args, **kwargs):
        if not self.pk:
            word = WordBank.get_random_word(self.difficulty)
            if word:
                self.word = word
                self.masked_word = '_' * len(word)
        super().save(*args, **kwargs)

    def start_game(self):
        self.start_time = timezone.now()
        players = list(self.players.all())
        self.current_turn = random.choice(players).user
        self.end_time = self.start_time + timedelta(
            minutes={1: 10, 2: 7, 3: 5}.get(self.difficulty, 10)
        )
        self.status = 2
        self.save()

    def is_expired(self):
        if self.status != 2 or not self.end_time:
            return False
        return timezone.now() > self.end_time

    def guess_letter(self, user, letter):
        if self.status != 2:
            return {'success': False, 'message': 'Game is not active'}
        if self.is_expired():
            self.status = 3
            self.save()
            return {'success': False, 'message': 'Game has expired'}
        if self.current_turn != user:
            return {'success': False, 'message': 'Not your turn'}
        try:
            player = self.players.get(user=user)
        except Player.DoesNotExist:
            return {'success': False, 'message': 'You are not part of this game'}

        letter = letter.lower()
        word_lower = self.word.lower()
        masked = list(self.masked_word)

        if not hasattr(self, 'guessed_letters') or self.guessed_letters is None:
            self.guessed_letters = ''

        unrevealed_indexes = [
            i for i in range(len(word_lower))
            if word_lower[i] == letter and masked[i] == '_'
        ]

        if unrevealed_indexes:
            # Only reveal the FIRST unrevealed occurrence of the letter
            index_to_reveal = unrevealed_indexes[0]
            masked[index_to_reveal] = self.word[index_to_reveal]  # Preserve original case
            self.masked_word = ''.join(masked)

            # Add to guessed letters only when we find a match
            if letter not in self.guessed_letters:
                self.guessed_letters += letter

            player.score += 20
            player.save()

            # Check if game is finished
            if '_' not in self.masked_word:
                self.status = 3  # Game finished

            result = {'success': True, 'message': 'Correct guess', 'points': 20}
        else:
            # Letter not found in word OR all instances already revealed
            # Add to guessed letters to track failed attempts
            if letter not in self.guessed_letters:
                self.guessed_letters += letter

            player.score -= 10
            player.save()
            result = {'success': True, 'message': 'Incorrect guess', 'points': -10}

        self.rotate_turn()
        self.save()
        return result

    def rotate_turn(self):
        players = list(self.players.all().order_by('id'))
        if len(players) != 2:
            return

        p1, p2 = players

        if not self.current_turn:
            self.current_turn = p1.user
        else:
            self.current_turn = p2.user if self.current_turn == p1.user else p1.user

    def end_game(self, timed_out=False):
        self.status = 3

        players = list(self.players.all().order_by('-score'))
        if len(players) != 2:
            return None, [], {}

        p1, p2 = players
        draw = p1.score == p2.score
        winner = None if draw else p1

        level_up_results = {}
        coin_rewards = {}

        time_bonus = 0
        if not timed_out and self.start_time and self.end_time:
            max_time = {
                1: 10 * 60,
                2: 7 * 60,
                3: 5 * 60
            }.get(self.difficulty, 10 * 60)

            actual_time = (self.end_time - self.start_time).total_seconds()
            if actual_time < max_time:
                time_bonus = int(50 * (1 - (actual_time / max_time)))

        xp_values = {
            'win': 80,
            'lose': 40,
            'draw': 60
        }
        coin_values = {
            'win': 60,
            'lose': 30,
            'draw': 45
        }

        for player in [p1, p2]:
            if draw:
                result = 'draw'
            else:
                result = 'win' if player == winner else 'lose'

            xp = xp_values[result] + time_bonus
            coins = coin_values[result]

            leveled_up, levels_gained = player.user.add_xp(xp)
            player.user.add_coins(coins)
            coin_rewards[player.user.id] = coins
            player.user.save()

            if leveled_up:
                level_up_results[player.user.id] = {
                    'username': player.user.username,
                    'new_level': player.user.level,
                    'levels_gained': levels_gained,
                    'xp_gained': xp
                }

            GameHistory.objects.create(
                game=self,
                player=player.user,
                score=player.score,
                result=result,
                guessed_word=self.word if '_' not in self.masked_word else self.masked_word
            )

        self.players.all().delete()
        self.save()
        return winner, list(level_up_results.values()), coin_rewards


class Player(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='game_players')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='players')
    score = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'game')


class GuessHistory(models.Model):
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='guesses')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='guesses')
    letter = models.CharField(max_length=1)
    is_correct = models.BooleanField()
    points = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        result = "correct" if self.is_correct else "incorrect"
        return f"{self.player.username} guessed '{self.letter}' ({result})"


class GameHistory(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='histories')
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='histories')
    score = models.IntegerField()
    result = models.CharField(max_length=10, choices=[('win', 'Win'), ('lose', 'Lose'), ('draw', 'Draw')])
    guessed_word = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
