import random

from django.core.exceptions import ValidationError
from django.db.models import Sum, F
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import User
from .models import Game, Player, GuessHistory, WordBank, GameHistory
from .serializers import (
    GameListSerializer, GameDetailSerializer, GameCreateSerializer,
    PlayerSerializer, GuessHistorySerializer, WordBankSerializer,
    GuessSerializer, GameHistorySerializer, WordGuessSerializer
)
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
)


@extend_schema_view(
    list=extend_schema(summary="List all games", parameters=[
        OpenApiParameter(name='status', type=str, description="Filter games by status")
    ]),
    retrieve=extend_schema(summary="Retrieve game details"),
    create=extend_schema(summary="Create a new game"),
    destroy=extend_schema(summary="Delete a game"),
    update=extend_schema(summary="Update a game"),
    partial_update=extend_schema(summary="Partially update a game"),
)
class GameViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_current_user_game(self, user):
        return Game.objects.filter(players__user=user, status=2).first()

    def get_queryset(self):
        status_filter = self.request.query_params.get('status', None)
        queryset = Game.objects.all()
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        active_games = queryset.filter(status=2)
        for game in active_games:
            if game.is_expired():
                game.end_game()

        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return GameCreateSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            return GameDetailSerializer
        return GameListSerializer

    def perform_create(self, serializer):
        user = self.request.user

        active_or_waiting_games = Game.objects.filter(creator=user, status__in=[1, 2])
        if active_or_waiting_games.exists():
            return Response({"error": "You already have an active or waiting game"},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer.save(creator=self.request.user)

    @extend_schema(
        summary="Join a game",
        request=None,
        responses={
            201: PlayerSerializer,
            400: OpenApiResponse(description="Game not joinable or user already joined")
        }
    )
    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        game = self.get_object()
        user = request.user

        if game.status != 1:
            return Response({"error": "Cannot join game that is not in waiting status"},
                            status=status.HTTP_400_BAD_REQUEST)

        if game.players.filter(user=user).exists():
            return Response({"error": "You are already in this game"},
                            status=status.HTTP_400_BAD_REQUEST)

        player = Player.objects.create(user=user, game=game)
        game.start_game()

        return Response({
            "player": PlayerSerializer(player).data,
            "game": GameDetailSerializer(game).data,
        }, status=status.HTTP_201_CREATED)


    @extend_schema(
        summary="Submit a guess",
        request=GuessSerializer,
        responses={
            200: OpenApiResponse(description="Guess processed successfully"),
            400: OpenApiResponse(description="Invalid guess or error processing")
        }
    )
    @action(detail=False, methods=['post'])
    def guess(self, request):
        game = self.get_current_user_game(user)
        user = request.user

        serializer = GuessSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        letter = serializer.validated_data['letter']
        result = game.guess_letter(user, letter)

        if not result['success']:
            return Response({"error": result['message']},
                            status=status.HTTP_400_BAD_REQUEST)

        player = game.players.get(user=user)
        GuessHistory.objects.create(
            player=player,
            game=game,
            letter=letter,
            is_correct=result['points'] > 0,
            points=result['points']
        )

        return Response({
            "result": result['message'],
            "points": result['points'],
            "game": GameDetailSerializer(game).data
        })

    @extend_schema(
        summary="Get guess history for a game",
        responses={200: GuessHistorySerializer(many=True)}
    )
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        game = self.get_object()
        guesses = game.guesses.all().order_by('-timestamp')
        serializer = GuessHistorySerializer(guesses, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Submit a full word guess",
        request=WordGuessSerializer,
        responses={
            200: OpenApiResponse(description="Word guess processed"),
            400: OpenApiResponse(description="Incorrect word guess or error")
        }
    )
    @action(detail=False, methods=['post'])
    def guess_word(self, request):
        game = self.get_current_user_game(user)
        user = request.user

        serializer = WordGuessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        guessed_word = serializer.validated_data['word'].lower()

        if game.status != 2:
            return Response({"error": "Game is not active."}, status=status.HTTP_400_BAD_REQUEST)

        if guessed_word == game.word.lower():
            game.winner = user
            game.save()

            player = game.players.get(user=user)
            GameHistory.objects.create(
                game=game,
                player=player,
                score=100,
                result='win',
                guessed_word=guessed_word
            )

            game.end_game()

            return Response({
                "message": "Correct! You win the game",
                "game": GameDetailSerializer(game).data
            })

        else:
            game.status = 3
            game.winner = game.players.exclude(user=user).first().user
            game.save()

            GameHistory.objects.create(
                game=game,
                player=user,
                score=-50,
                result='lose',
                guessed_word=guessed_word
            )

            game.end_game()

            return Response({
                "message": "Incorrect guess. You lost the game",
                "game": GameDetailSerializer(game).data
            })

    @extend_schema(
        summary="reveal a letter",
        responses={
            200: OpenApiResponse(description="Word guess processed"),
            400: OpenApiResponse(description="Incorrect word guess or error")
        }
    )
    @action(detail=False, methods=['post'])
    def reveal_letter(self, request):
        game = self.get_current_user_game(user)
        user = request.user

        if game.status != 2:
            return Response({"error": "Game not active"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            player = game.players.get(user=user)
        except Player.DoesNotExist:
            return Response({"error": "Not in game"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if there are hidden letters
        if '_' not in game.masked_word:
            return Response({"error": "No hidden letters to reveal"}, status=status.HTTP_400_BAD_REQUEST)

        reveal_cost = 30

        if not user.deduct_coins(reveal_cost):
            return Response({"error": "Not enough coins"}, status=status.HTTP_400_BAD_REQUEST)

        hidden_positions = [i for i, char in enumerate(game.masked_word) if char == '_']

        pos = random.choice(hidden_positions)

        new_masked = list(game.masked_word)
        new_masked[pos] = game.word[pos]
        game.masked_word = ''.join(new_masked)
        game.save()

        return Response({
            "message": f"Letter revealed at position {pos + 1}",
            "masked_word": game.masked_word,
            "coins_spent": reveal_cost,
            "remaining_coins": user.coin
        })


@extend_schema_view(
    list=extend_schema(summary="List all players", parameters=[
        OpenApiParameter(name='game', type=int, description="Filter by game ID")
    ]),
    retrieve=extend_schema(summary="Retrieve player details")
)
class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PlayerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        game_id = self.request.query_params.get('game', None)
        if game_id:
            return Player.objects.filter(game_id=game_id).order_by('-score')
        return Player.objects.all().order_by('-score')


@extend_schema_view(
    list=extend_schema(summary="List all words in word bank"),
    retrieve=extend_schema(summary="Get word details"),
    create=extend_schema(summary="Add a new word"),
    update=extend_schema(summary="Update a word"),
    partial_update=extend_schema(summary="Partially update a word"),
    destroy=extend_schema(summary="Delete a word")
)
class WordBankViewSet(viewsets.ModelViewSet):
    queryset = WordBank.objects.all()
    serializer_class = WordBankSerializer
    permission_classes = [permissions.IsAdminUser]


@extend_schema_view(
    list=extend_schema(summary="List user's game history"),
    retrieve=extend_schema(summary="Get game history detail"),
    create=extend_schema(summary="Create a new game history record"),
    update=extend_schema(summary="Update a game history record"),
    partial_update=extend_schema(summary="Partially update a game history record"),
    destroy=extend_schema(summary="Delete a game history record")
)
class GameHistoryViewSet(viewsets.ModelViewSet):
    queryset = GameHistory.objects.all()
    serializer_class = GameHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(player=self.request.user, game__status=1)

    def perform_create(self, serializer):
        serializer.save(player=self.request.user)


@extend_schema_view(
    list=extend_schema(summary="Top 10 players based on total score")
)
class LeaderboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        top_players = (
            User.objects
            .values('username')
            .annotate(total_score=F('xp'))  # Using the score field directly from User model
            .order_by('-total_score')[:10]
        )
        return Response(top_players)
