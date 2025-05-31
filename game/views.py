from rest_framework import viewsets, status, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsGameAdmin, IsAdminOrCreatorWhileWaiting
from .game_swagger import *
from .serializers import *

from .services import GameService
from .mixins import GameMixin, ThrottleMixin
from .throttles import *


@GAME_VIEWSET_SCHEMA
class GameViewSet(GameMixin, ThrottleMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ApiDefaultThrottle]

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAdminOrCreatorWhileWaiting()]

        return super().get_permissions()

    def get_throttles(self):
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

        queryset = queryset.filter(status=1)

        self.check_active_games()
        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return GameCreateSerializer
        elif self.action in ['retrieve']:
            if self.get_object().status == 1:
                return GameCreateSerializer
            return GameDetailSerializer
        elif self.action in ['update', 'partial_update']:
            return GameCreateSerializer
        return GameListSerializer

    def perform_create(self, serializer):
        user = self.request.user

        if GameService.check_active_games(user):
            self.permission_denied(
                self.request,
                message="You already have an active or waiting game"
            )

        game = serializer.save(creator=user)
        GameService.invalidate_user_game_caches(user.id)

        GameService.cache_active_game(game)

    @JOIN_GAME_SCHEMA
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
        GameService.cache_active_game(game)

        return Response({
            "player": PlayerSerializer(player).data,
            "game": GameDetailSerializer(game).data,
        }, status=status.HTTP_201_CREATED)

    @GUESS_LETTER_SCHEMA
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
            game.end_game()
            return Response({
                "message": "Correct! You win the game",
                "game": GameDetailSerializer(game).data
            })

        return Response({
            "result": result['message'],
            "points": result['points'],
            "game": GameDetailSerializer(game).data
        })

    @GAME_HISTORY_SCHEMA
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        game = self.get_object()
        guesses = game.guesses.all().order_by('-timestamp')
        serializer = GuessHistorySerializer(guesses, many=True)
        return Response(serializer.data)

    @GUESS_WORD_SCHEMA
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

    @REVEAL_LETTER_SCHEMA
    @action(detail=False, methods=['post'])
    def reveal_letter(self, request):
        result = GameService.reveal_letter(request.user)

        if not result['success']:
            return Response(
                {"error": result['message']},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(result)


@WORDBANK_VIEWSET_SCHEMA
class WordBankViewSet(viewsets.ModelViewSet):
    queryset = WordBank.objects.all()
    serializer_class = WordBankSerializer
    permission_classes = [IsGameAdmin]
    throttle_classes = [ApiDefaultThrottle]


@GAMEHISTORY_VIEWSET_SCHEMA
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
        return GameHistory.objects.filter(player=self.request.user)

    def perform_create(self, serializer):
        serializer.save(player=self.request.user)


@LEADERBOARD_VIEWSET_SCHEMA
class LeaderboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ApiAnonThrottle]

    def list(self, request):
        top_players = GameService.leaderboard()
        return Response(top_players)
