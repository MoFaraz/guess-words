from drf_spectacular.utils import extend_schema, OpenApiResponse
from .serializers import RegisterSerializer, UserProfileSerializer, CustomTokenObtainPairSerializer


class AccountSwaggerDocs:
    """
    Swagger documentation for Account ViewSet endpoints
    """

    register = extend_schema(
        summary="Register a new user",
        description="Create a new user account with username, email, and password",
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(description="User successfully created", response=UserProfileSerializer),
            400: OpenApiResponse(description="Bad request, validation error")
        }
    )

    profile = extend_schema(
        summary="Get user profile",
        description="Retrieve the authenticated user's profile information",
        responses={
            200: UserProfileSerializer,
            401: OpenApiResponse(description="Unauthorized")
        }
    )

    update_profile = extend_schema(
        summary="Update user profile",
        description="Update the authenticated user's profile information",
        request=UserProfileSerializer,
        responses={
            200: UserProfileSerializer,
            400: OpenApiResponse(description="Bad request, validation error"),
            401: OpenApiResponse(description="Unauthorized")
        }
    )

    kick_user = extend_schema(
        summary="Kick user (Admin only)",
        description="Delete a user account from the system. Only game administrators can perform this action.",
        responses={
            200: OpenApiResponse(description="User successfully kicked"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden - Admin access required"),
            404: OpenApiResponse(description="User not found")
        }
    )

    reset_coins = extend_schema(
        summary="Reset user coins (Admin only)",
        description="Reset a user's coin balance to 0. Only game administrators can perform this action.",
        responses={
            200: OpenApiResponse(description="User coins successfully reset"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden - Admin access required"),
            404: OpenApiResponse(description="User not found")
        }
    )

    make_admin = extend_schema(
        summary="Grant Admin Role To A Player(Admin only)",
        description="If You Are An Admin You Can Grant A Player To Admin Using Player's Id",
        responses={
            200: OpenApiResponse(description="User Role Successfully Changed To Admin"),
            400: OpenApiResponse(description="User Already Is An Admin"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden - Admin access required"),
            404: OpenApiResponse(description="User not found")
        }
    )


class AuthSwaggerDocs:

    token_obtain_pair = extend_schema(
        summary="Obtain JWT token pair",
        description="Login with username/email and password to obtain access and refresh tokens",
        request=CustomTokenObtainPairSerializer,
        responses={
            200: OpenApiResponse(description="Tokens successfully generated"),
            401: OpenApiResponse(description="Invalid credentials")
        }
    )