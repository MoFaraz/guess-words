from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse,
    OpenApiExample
)
from drf_spectacular.types import OpenApiTypes
from .serializers import (
    GameListSerializer, GameDetailSerializer, GameCreateSerializer,
    PlayerSerializer, GuessHistorySerializer, WordBankSerializer,
    GuessSerializer, GameHistorySerializer, WordGuessSerializer
)


# Common OpenAPI parameters
STATUS_PARAMETER = OpenApiParameter(
    name='status',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    description="Filter games by status (1=Waiting, 2=Active, 3=Completed)",
    enum=[1, 2, 3]
)

# Common responses
GAME_NOT_FOUND_RESPONSE = OpenApiResponse(
    description="Game not found",
    examples=[
        OpenApiExample(
            'Game not found',
            value={"error": "Game not found"},
            status_codes=['404']
        )
    ]
)

PERMISSION_DENIED_RESPONSE = OpenApiResponse(
    description="Permission denied",
    examples=[
        OpenApiExample(
            'Permission denied',
            value={"error": "You do not have permission to perform this action"},
            status_codes=['403']
        )
    ]
)

VALIDATION_ERROR_RESPONSE = OpenApiResponse(
    description="Validation error",
    examples=[
        OpenApiExample(
            'Validation error',
            value={"error": "Invalid input data"},
            status_codes=['400']
        )
    ]
)


# GameViewSet schemas
GAME_VIEWSET_SCHEMA = extend_schema_view(
    list=extend_schema(
        summary="List all games",
        description="Retrieve a list of all active games. Games are filtered to show only active status by default.",
        parameters=[STATUS_PARAMETER],
        responses={
            200: GameListSerializer(many=True),
            401: OpenApiResponse(description="Authentication required")
        },
        examples=[
            OpenApiExample(
                'Success response',
                value=[
                    {
                        "id": 1,
                        "creator": "john_doe",
                        "difficulty": 1,
                        "status": 2,
                        "created_at": "2024-01-15T10:30:00Z",
                        "players_count": 2
                    }
                ]
            )
        ]
    ),
    retrieve=extend_schema(
        summary="Retrieve game details",
        description="Get detailed information about a specific game including current game state, players, and masked word.",
        responses={
            200: GameDetailSerializer,
            404: GAME_NOT_FOUND_RESPONSE,
            401: OpenApiResponse(description="Authentication required")
        },
        examples=[
            OpenApiExample(
                'Game details',
                value={
                    "id": 1,
                    "creator": "john_doe",
                    "difficulty": 2,
                    "masked_word": "py___n",
                    "status": 2,
                    "current_turn": "jane_doe",
                    "players": [
                        {"user": "john_doe", "score": 20},
                        {"user": "jane_doe", "score": 10}
                    ],
                    "start_time": "2024-01-15T10:30:00Z",
                    "end_time": "2024-01-15T10:37:00Z"
                }
            )
        ]
    ),
    create=extend_schema(
        summary="Create a new game",
        description="Create a new word guessing game. Only one active/waiting game per user is allowed.",
        request=GameCreateSerializer,
        responses={
            201: GameDetailSerializer,
            400: OpenApiResponse(
                description="Cannot create game",
                examples=[
                    OpenApiExample(
                        'Already has active game',
                        value={"error": "You already have an active or waiting game"}
                    )
                ]
            ),
            401: OpenApiResponse(description="Authentication required")
        },
        examples=[
            OpenApiExample(
                'Create game request',
                value={"difficulty": 2}
            )
        ]
    ),
    destroy=extend_schema(
        summary="Delete a game",
        description="Delete a game (only if you're the creator or admin)",
        responses={
            204: OpenApiResponse(description="Game deleted successfully"),
            403: PERMISSION_DENIED_RESPONSE,
            404: GAME_NOT_FOUND_RESPONSE
        }
    ),
    update=extend_schema(
        summary="Update a game",
        description="Update game details (only creator or admin)",
        responses={
            200: GameDetailSerializer,
            403: PERMISSION_DENIED_RESPONSE,
            404: GAME_NOT_FOUND_RESPONSE
        }
    ),
    partial_update=extend_schema(
        summary="Partially update a game",
        description="Partially update game details (only creator or admin)",
        responses={
            200: GameDetailSerializer,
            403: PERMISSION_DENIED_RESPONSE,
            404: GAME_NOT_FOUND_RESPONSE
        }
    ),
)

# Game action schemas
JOIN_GAME_SCHEMA = extend_schema(
    summary="Join a game",
    description="Join a waiting game. Game must be in 'Waiting For Players' status and you cannot already be a player.",
    request=None,
    responses={
        201: OpenApiResponse(
            description="Successfully joined game",
            examples=[
                OpenApiExample(
                    'Join success',
                    value={
                        "player": {
                            "user": "jane_doe",
                            "score": 0
                        },
                        "game": {
                            "id": 1,
                            "status": 2,
                            "masked_word": "______",
                            "current_turn": "john_doe"
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Cannot join game",
            examples=[
                OpenApiExample(
                    'Game not joinable',
                    value={"error": "Cannot join game that is not in waiting status"}
                ),
                OpenApiExample(
                    'Already joined',
                    value={"error": "You are already in this game"}
                )
            ]
        )
    }
)

GUESS_LETTER_SCHEMA = extend_schema(
    summary="Submit a letter guess",
    description="Submit a single letter guess for your active game. Awards +20 points for correct, -10 for incorrect.",
    request=GuessSerializer,
    responses={
        200: OpenApiResponse(
            description="Guess processed successfully",
            examples=[
                OpenApiExample(
                    'Correct guess',
                    value={
                        "result": "Correct guess",
                        "points": 20,
                        "game": {
                            "masked_word": "py_h_n",
                            "status": 2
                        }
                    }
                ),
                OpenApiExample(
                    'Game won',
                    value={
                        "message": "Correct! You win the game",
                        "game": {
                            "masked_word": "python",
                            "status": 3
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Invalid guess or error processing",
            examples=[
                OpenApiExample(
                    'No active game',
                    value={"error": "No active game"}
                ),
                OpenApiExample(
                    'Not your turn',
                    value={"error": "Not your turn"}
                ),
                OpenApiExample(
                    'Game expired',
                    value={"error": "Game has expired"}
                )
            ]
        )
    },
    examples=[
        OpenApiExample(
            'Letter guess',
            value={"letter": "a"}
        )
    ]
)

GUESS_WORD_SCHEMA = extend_schema(
    summary="Submit a full word guess",
    description="Submit a complete word guess. Correct guess wins the game, incorrect guess loses immediately.",
    request=WordGuessSerializer,
    responses={
        200: OpenApiResponse(
            description="Word guess processed",
            examples=[
                OpenApiExample(
                    'Correct word',
                    value={
                        "message": "Correct! You win the game",
                        "game": {
                            "status": 3,
                            "masked_word": "python"
                        }
                    }
                ),
                OpenApiExample(
                    'Incorrect word',
                    value={
                        "message": "Incorrect guess. You lost the game",
                        "game": {
                            "status": 3
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Incorrect word guess or error",
            examples=[
                OpenApiExample(
                    'Game not active',
                    value={"error": "Game is not active"}
                )
            ]
        )
    },
    examples=[
        OpenApiExample(
            'Word guess',
            value={"word": "python"}
        )
    ]
)

REVEAL_LETTER_SCHEMA = extend_schema(
    summary="Reveal a letter",
    description="Spend 30 coins to reveal a random hidden letter in your active game.",
    responses={
        200: OpenApiResponse(
            description="Letter revealed",
            examples=[
                OpenApiExample(
                    'Letter revealed',
                    value={
                        "message": "Letter revealed at position 3",
                        "masked_word": "py_h_n",
                        "coins_spent": 30,
                        "remaining_coins": 170
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Error revealing letter",
            examples=[
                OpenApiExample(
                    'Not enough coins',
                    value={"error": "Not enough coins"}
                ),
                OpenApiExample(
                    'No hidden letters',
                    value={"error": "No hidden letters to reveal"}
                ),
                OpenApiExample(
                    'Game not active',
                    value={"error": "Game not active"}
                )
            ]
        )
    }
)

GAME_HISTORY_SCHEMA = extend_schema(
    summary="Get guess history for a game",
    description="Retrieve all letter guesses made in a specific game, ordered by most recent first.",
    responses={
        200: GuessHistorySerializer(many=True),
        404: GAME_NOT_FOUND_RESPONSE
    },
    examples=[
        OpenApiExample(
            'Guess history',
            value=[
                {
                    "player": "john_doe",
                    "letter": "a",
                    "is_correct": True,
                    "points": 20,
                    "timestamp": "2024-01-15T10:35:00Z"
                },
                {
                    "player": "jane_doe",
                    "letter": "x",
                    "is_correct": False,
                    "points": -10,
                    "timestamp": "2024-01-15T10:33:00Z"
                }
            ]
        )
    ]
)

# WordBankViewSet schemas
WORDBANK_VIEWSET_SCHEMA = extend_schema_view(
    list=extend_schema(
        summary="List all words in word bank",
        description="Retrieve all words available for games (Admin only)",
        responses={
            200: WordBankSerializer(many=True),
            403: PERMISSION_DENIED_RESPONSE
        }
    ),
    retrieve=extend_schema(
        summary="Get word details",
        description="Get details of a specific word (Admin only)",
        responses={
            200: WordBankSerializer,
            403: PERMISSION_DENIED_RESPONSE,
            404: OpenApiResponse(description="Word not found")
        }
    ),
    create=extend_schema(
        summary="Add a new word",
        description="Add a new word to the word bank (Admin only)",
        responses={
            201: WordBankSerializer,
            403: PERMISSION_DENIED_RESPONSE,
            400: VALIDATION_ERROR_RESPONSE
        }
    ),
    update=extend_schema(
        summary="Update a word",
        description="Update an existing word (Admin only)",
        responses={
            200: WordBankSerializer,
            403: PERMISSION_DENIED_RESPONSE,
            404: OpenApiResponse(description="Word not found")
        }
    ),
    partial_update=extend_schema(
        summary="Partially update a word",
        description="Partially update an existing word (Admin only)",
        responses={
            200: WordBankSerializer,
            403: PERMISSION_DENIED_RESPONSE,
            404: OpenApiResponse(description="Word not found")
        }
    ),
    destroy=extend_schema(
        summary="Delete a word",
        description="Remove a word from the word bank (Admin only)",
        responses={
            204: OpenApiResponse(description="Word deleted successfully"),
            403: PERMISSION_DENIED_RESPONSE,
            404: OpenApiResponse(description="Word not found")
        }
    )
)

# GameHistoryViewSet schemas
GAMEHISTORY_VIEWSET_SCHEMA = extend_schema_view(
    list=extend_schema(
        summary="List your game history",
        description="Retrieve your personal game history",
        responses={
            200: GameHistorySerializer(many=True),
            401: OpenApiResponse(description="Authentication required")
        }
    ),
    retrieve=extend_schema(
        summary="Get game history details",
        description="Get details of a specific game history entry",
        responses={
            200: GameHistorySerializer,
            404: OpenApiResponse(description="Game history not found")
        }
    ),
    destroy=extend_schema(
        summary="Delete game history",
        description="Delete a game history entry",
        responses={
            204: OpenApiResponse(description="Game history deleted"),
            404: OpenApiResponse(description="Game history not found")
        }
    )
)

# LeaderboardViewSet schemas
LEADERBOARD_SCHEMA = extend_schema(
    summary="Top 10 players based on total score",
    description="Get the leaderboard showing top 10 players ranked by their total XP/score",
    responses={
        200: OpenApiResponse(
            description="Leaderboard data",
            examples=[
                OpenApiExample(
                    'Top players',
                    value=[
                        {
                            "username": "pro_player",
                            "total_score": 2500
                        },
                        {
                            "username": "word_master",
                            "total_score": 2100
                        },
                        {
                            "username": "guess_king",
                            "total_score": 1800
                        }
                    ]
                )
            ]
        )
    }
)

LEADERBOARD_VIEWSET_SCHEMA = extend_schema_view(
    list=LEADERBOARD_SCHEMA
)