from django.utils import timezone
from rest_framework import serializers
from .models import Game, Player, GuessHistory, WordBank, GameHistory
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class PlayerSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Player
        fields = ['id', 'user', 'score']


class GuessHistorySerializer(serializers.ModelSerializer):
    player = serializers.StringRelatedField()

    class Meta:
        model = GuessHistory
        fields = ['id', 'player', 'letter', 'is_correct', 'points', 'timestamp']


class GameListSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    player_count = serializers.SerializerMethodField()

    class Meta:
        model = Game
        fields = ['id', 'difficulty', 'status', 'creator', 'player_count', 'created_at']

    def get_player_count(self, obj) -> int:
        return obj.players.count()


class GameHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GameHistory
        fields = '__all__'


class WordGuessSerializer(serializers.Serializer):
    word = serializers.CharField(max_length=100, min_length=3)


class GameDetailSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    players = PlayerSerializer(many=True, read_only=True)
    current_turn = UserSerializer(read_only=True)
    time_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Game
        fields = [
            'id', 'difficulty', 'masked_word', 'status', 'creator',
            'players', 'current_turn', 'start_time', 'end_time',
            'time_remaining', 'created_at', 'updated_at'
        ]
        read_only_fields = ['word', 'masked_word', 'start_time', 'end_time', 'status']

    def get_time_remaining(self, obj) -> int:
        if obj.status != 2 or not obj.end_time:
            return None

        now = timezone.now()
        if now > obj.end_time:
            return 0

        seconds_remaining = (obj.end_time - now).total_seconds()
        return int(seconds_remaining)


class GameCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = ['pk', 'difficulty']

    def validate_difficulty(self, value):
        valid_difficulties = dict(Game.DIFFICULTY_CHOICES).keys()
        if value not in valid_difficulties:
            raise serializers.ValidationError(f"Difficulty must be one of {list(valid_difficulties)}")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        game = Game.objects.create(**validated_data)

        Player.objects.create(user=user, game=game)

        return game


class GuessSerializer(serializers.Serializer):
    letter = serializers.CharField(max_length=1)

    def validate_letter(self, value):
        if len(value) != 1 or not value.isalpha():
            raise serializers.ValidationError("Must be a single alphabetic character")
        return value


class WordBankSerializer(serializers.ModelSerializer):
    class Meta:
        model = WordBank
        fields = ['id', 'word', 'difficulty']
