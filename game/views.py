from django.db.models import F
from rest_framework import viewsets, status, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsGameAdmin
from .models import Game, Player, WordBank, GameHistory
from .serializers import (
    GameListSerializer, GameDetailSerializer, GameCreateSerializer,
    PlayerSerializer, GuessHistorySerializer, WordBankSerializer,
    GuessSerializer, GameHistorySerializer, WordGuessSerializer
)
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
)

from .services import GameService
from .mixins import GameMixin, ThrottleMixin
from .throttles import (
    GameActionThrottle, GameCreateThrottle,
    ApiDefaultThrottle, ApiAnonThrottle
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
class GameViewSet(GameMixin, ThrottleMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ApiDefaultThrottle]

    def get_throttles(self):
        """Apply different throttles based on action"""
        if self.action == 'create':
            self.throttle_classes = [GameCreateThrottle]
        elif self.action in ['guess', 'guess_word', 'reveal_letter', 'join']:
            self.throttle_classes = [GameActionThrottle]
        return super().get_throttles()

    def get_queryset(self):
        status_filter = self.request.query_params.get('status', None)
        queryset = Game.objects.all()

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        self.check_active_games()
        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return GameCreateSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            return GameDetailSerializer
        return GameListSerializer

    def perform_create(self, serializer):
        user = self.request.user

        if GameService.check_active_games(user):
            self.permission_denied(
                self.request,
                message="You already have an active or waiting game"
            )

        serializer.save(creator=user)

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
            return Response(
                {"error": "Cannot join game that is not in waiting status"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if game.players.filter(user=user).exists():
            return Response(
                {"error": "You are already in this game"},
                status=status.HTTP_400_BAD_REQUEST
            )

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
        serializer = GuessSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        result = GameService.process_guess(
            user=request.user,
            letter=serializer.validated_data['letter']
        )

        if not result['success']:
            return Response(
                {"error": result['message']},
                status=status.HTTP_400_BAD_REQUEST
            )

        game = result['game']
        if game.status == 3:
            return Response({
                "message": "Correct! You win the game",
                "game": GameDetailSerializer(game).data
            })

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
        serializer = WordGuessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = GameService.process_word_guess(
            user=request.user,
            guessed_word=serializer.validated_data['word']
        )

        if not result['success'] and not result['game']:
            return Response(
                {"error": result['message']},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            "message": result['message'],
            "game": GameDetailSerializer(result['game']).data
        })

    @extend_schema(
        summary="Reveal a letter",
        responses={
            200: OpenApiResponse(description="Letter revealed"),
            400: OpenApiResponse(description="Error revealing letter")
        }
    )
    @action(detail=False, methods=['post'])
    def reveal_letter(self, request):
        result = GameService.reveal_letter(request.user)

        if not result['success']:
            return Response(
                {"error": result['message']},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(result)


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
    permission_classes = [IsGameAdmin]
    throttle_classes = [ApiDefaultThrottle]


class GameHistoryViewSet(mixins.CreateModelMixin,
                         mixins.RetrieveModelMixin,
                         mixins.UpdateModelMixin,
                         mixins.DestroyModelMixin,
                         mixins.ListModelMixin,
                         viewsets.GenericViewSet):
    serializer_class = GameHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ApiDefaultThrottle]

    def get_queryset(self):
        return GameHistory.objects.filter(player=self.request.user, game__status=1)

    def perform_create(self, serializer):
        serializer.save(player=self.request.user)


@extend_schema_view(
    list=extend_schema(summary="Top 10 players based on total score")
)
class LeaderboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ApiAnonThrottle]

    def list(self, request):
        top_players = (
            User.objects
            .values('username')
            .annotate(total_score=F('xp'))
            .order_by('-total_score')[:10]
        )
        return Response(top_players)