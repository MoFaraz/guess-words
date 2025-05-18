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
    word = models.CharField(max_length=20)
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
        self.current_turn = self.players.first().user
        self.end_time = self.start_time + timedelta(
            minutes={1: 10, 2: 7, 3: 5}.get(self.difficulty, 10)
        )
        self.status = 2
        self.save()

    def is_expired(self):
        if self.status != 2 or not self.end_time:
            return False
        return timezone.now() > self.end_time

    def get_winner(self):
        player_scores = {}
        for player in self.players.all():
            player_scores[player.user.id] = player.score

        if not player_scores:
            return None

        winner_id = max(player_scores, key=player_scores.get)
        return self.players.get(user_id=winner_id)

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
        if letter in self.word.lower():
            new_masked = list(self.masked_word)
            for i, char in enumerate(self.word.lower()):
                if char == letter:
                    new_masked[i] = self.word[i]  # Use original case

            self.masked_word = ''.join(new_masked)
            player.score += 20
            player.save()

            if '_' not in self.masked_word:
                self.status = 3

            result = {'success': True, 'message': 'Correct guess', 'points': 20}
        else:
            player.score -= 10
            player.save()
            result = {'success': True, 'message': 'Incorrect guess', 'points': -10}

        self._rotate_turn()
        self.save()

        return result

    def _rotate_turn(self):
        players = list(self.players.all().order_by('id'))
        if not players:
            return

        if not self.current_turn:
            self.current_turn = players[0].user
            return

        for i, player in enumerate(players):
            if player.user == self.current_turn:
                next_index = (i + 1) % len(players)
                self.current_turn = players[next_index].user
                return

        self.current_turn = players[0].user

    def end_game(self, timed_out=False):
        """End the game and distribute XP and coins to players"""
        self.status = 3

        # Get all players in descending order of score
        players = list(self.players.all().order_by('-score'))
        winner = players[0] if players else None

        level_up_results = []
        coin_rewards = {}

        if len(players) >= 2:
            difficulty_multiplier = {
                1: 1.0,  # Easy
                2: 1.5,  # Medium
                3: 2.0  # Hard
            }.get(self.difficulty, 1.0)

            word_length_modifier = len(self.word) / 5

            time_bonus = 0
            if not timed_out and self.start_time and self.end_time:
                max_time = {
                    1: 10 * 60,  # Easy: 10 minutes in seconds
                    2: 7 * 60,  # Medium: 7 minutes in seconds
                    3: 5 * 60  # Hard: 5 minutes in seconds
                }.get(self.difficulty, 10 * 60)

                actual_time = (self.end_time - self.start_time).total_seconds()
                if actual_time < max_time:
                    time_bonus = 50 * (1 - (actual_time / max_time))

            word_completion_bonus = 0
            if not timed_out and '_' not in self.masked_word:
                word_completion_bonus = 30 * difficulty_multiplier

            for i, player in enumerate(players):
                if i == 0:
                    position_xp = 50
                    coins = 50 * difficulty_multiplier
                elif i == 1:
                    position_xp = 30
                    coins = 30 * difficulty_multiplier

                score_xp = max(0, player.score // 5)

                participation_bonus = 10

                if not timed_out and '_' not in self.masked_word:
                    coins += 10 * difficulty_multiplier

                total_xp = max(int((position_xp + score_xp + word_completion_bonus + time_bonus + participation_bonus) *
                                   difficulty_multiplier * word_length_modifier), 15)

                leveled_up, levels_gained = player.user.add_xp(total_xp)

                player.user.add_coins(int(coins))
                coin_rewards[player.user.id] = int(coins)

                player.user.save()

                if leveled_up:
                    level_up_results.append({
                        'user_id': player.user.id,
                        'username': player.user.username,
                        'new_level': player.user.level,
                        'levels_gained': levels_gained,
                        'xp_gained': total_xp
                    })

                GameHistory.objects.create(
                    game=self,
                    player=player,
                    score=player.score,
                    result='win' if i == 0 else 'lose',
                    guessed_word=self.word if '_' not in self.masked_word else self.masked_word
                )

        self.save()
        return winner, level_up_results, coin_rewards


class Player(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='game_players')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='players')
    score = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'game')
        verbose_name = 'Player'
        verbose_name_plural = 'Players'

    def __str__(self):
        return f"{self.user.username}"


class GuessHistory(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='guesses')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='guesses')
    letter = models.CharField(max_length=1)
    is_correct = models.BooleanField()
    points = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        result = "correct" if self.is_correct else "incorrect"
        return f"{self.player.user.username} guessed '{self.letter}' ({result})"


class GameHistory(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='histories')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='histories')
    score = models.IntegerField()
    result = models.CharField(max_length=10, choices=[('win', 'Win'), ('lose', 'Lose'), ('draw', 'Draw')])
    guessed_word = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
