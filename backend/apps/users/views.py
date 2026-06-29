"""
Views for the users module.

This module implements the API endpoints for:
- Registration of new users
- Authentication and logged-in user profile management
- Complete CRUD of users (with permissions)
- User profile management
- Google OAuth 2.0 + OIDC login
"""

import logging

from django.conf import settings
from django.shortcuts import redirect

from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Profile, User
from .permissions import IsOwnerOrReadOnly
from .serializers import (
    CustomTokenObtainPairSerializer,
    ProfileSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserRegistrationSerializer,
    UserUpdateSerializer,
)
from .services.google_oauth import GoogleOAuthService
from .throttles import LoginRateThrottle, OAuthRateThrottle, RegistrationThrottle

logger = logging.getLogger(__name__)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Login view with rate limiting and case-insensitive email."""

    throttle_classes = [LoginRateThrottle]
    serializer_class = CustomTokenObtainPairSerializer


class UserRegistrationView(APIView):
    """
    Public endpoint for new user registration.

    This view handles the creation of new user accounts in the system.
    It accepts registration data including username, email, and password,
    validates the input, and creates a new user account if all validations pass.

    Permissions:
        - AllowAny: No authentication required, publicly accessible endpoint.

    Attributes:
        permission_classes (list): List of permission classes applied to this view.

    Methods:
        post: Creates a new user account with the provided registration data.
    """

    permission_classes = [AllowAny]
    throttle_classes = [RegistrationThrottle]

    def post(self, request):
        """
        Create a new user account in the system.

        Validates the registration data using UserRegistrationSerializer and creates
        a new user account if all validation checks pass (username uniqueness,
        email format, password strength, password confirmation match, etc.).

        Args:
            request: HTTP request object containing user registration data.
                Expected fields: username, email, password, confirm_password.

        Returns:
            Response: JSON response with one of the following:
                - 201 CREATED: User successfully created with serialized user data.
                - 400 BAD REQUEST: Validation failed with error details.

        Example:
            POST /api/auth/register/
            {
                "username": "johndoe",
                "email": "john@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!"
            }
        """
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.refresh_from_db()
            response_serializer = UserDetailSerializer(user)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrentUserView(APIView):
    """
    Endpoint for authenticated users to view and edit their own profile.

    This view allows logged-in users to retrieve their profile information
    and update their own account details.

    Permissions:
        - IsAuthenticated: Only authenticated users can access this endpoint.

    Attributes:
        permission_classes (list): List of permission classes applied to this view.

    Methods:
        get: Retrieves the current user's profile information.
        patch: Updates the current user's profile information.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Retrieve the current user's profile information.

        Returns the authenticated user's details serialized with UserDetailSerializer.

        Args:
            request: HTTP request object from an authenticated user.

        Returns:
            Response: JSON response with the user's profile data (status 200).
        """
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        """
        Update the current user's profile information.

        Validates the update data using UserUpdateSerializer and updates
        the authenticated user's account if validation passes. Only specific
        fields can be updated through this endpoint.

        Args:
            request: HTTP request object containing user update data.
                Allowed fields: first_name, last_name, phone.

        Returns:
            Response: JSON response with one of the following:
                - 200 OK: User successfully updated with serialized user data.
                - 400 BAD REQUEST: Validation failed with error details.
        """
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for complete user management.

    Provides CRUD endpoints for users with:
    - Paginated and filterable listing
    - Complete details with nested profile
    - Updates with validations
    - Search by username/email
    - Customizable ordering

    Permissions:
        - IsOwnerOrReadOnly: authenticated only; staff see all records,
          others see and edit only their own (anonymous access is rejected)
    """

    # Base configuration
    queryset = User.objects.all()
    permission_classes = [IsOwnerOrReadOnly]

    # Filters and search
    filterset_fields = ["is_instructor", "is_active"]
    search_fields = ["username", "email"]
    ordering_fields = ["username", "date_joined"]
    ordering = ["-date_joined"]

    def get_throttles(self):
        """Throttle account creation as registration; defaults elsewhere."""
        if self.action == "create":
            return [RegistrationThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        """Scope reads: staff see all users; everyone else only their own record."""
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return User.objects.none()
        qs = User.objects.select_related("profile")  # retrieve nests the profile
        if user.is_staff:
            return qs
        return qs.filter(pk=user.pk)

    # Dynamic serializers
    def get_serializer_class(self):
        """
        Returns the appropriate serializer for each action.

        Returns:
            Serializer class based on self.action:
            - list: UserListSerializer (minimal fields)
            - create: UserRegistrationSerializer (with password hashing)
            - retrieve: UserDetailSerializer (complete with nested)
            - update/partial_update: UserUpdateSerializer (editable fields)
            - default: UserDetailSerializer
        """
        if self.action == "list":
            return UserListSerializer
        elif self.action == "create":
            return UserRegistrationSerializer
        elif self.action == "retrieve":
            return UserDetailSerializer
        elif self.action in ["update", "partial_update"]:
            return UserUpdateSerializer
        return UserDetailSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new user via UserViewSet.

        Override default create to return UserDetailSerializer in response,
        ensuring profile is nested and complete user data is returned.
        This makes the response consistent with UserRegistrationView.

        Args:
            request: HTTP request with user registration data.

        Returns:
            Response with UserDetailSerializer data (includes nested profile).
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.refresh_from_db()  # Reload to include profile created by signal
        response_serializer = UserDetailSerializer(user)
        headers = self.get_success_headers(response_serializer.data)
        return Response(
            response_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class ProfileViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for user profile read and update.

    Profiles are created automatically by signal on user creation and are
    1:1 with the user, so create and destroy are intentionally **not**
    exposed (POST/DELETE → 405). Provides:
    - Paginated listing (scoped to the owner; staff see all)
    - Retrieve with related user information
    - Update of the owner's own profile
    - Optimized queries with select_related

    Permissions:
        - IsOwnerOrReadOnly: authenticated only; staff see all records,
          others see and edit only their own (anonymous access is rejected)
    """

    # Base configuration
    queryset = Profile.objects.select_related("user")
    serializer_class = ProfileSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        """Scope reads: staff see all profiles; everyone else only their own."""
        qs = Profile.objects.select_related("user")
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return Profile.objects.none()
        if user.is_staff:
            return qs
        return qs.filter(user=user)


class GoogleLoginView(APIView):
    """Initiate the Google OAuth 2.0 Authorization Code flow.

    Generates a cryptographically random state and nonce, stores them in
    the session, then redirects the user to Google's authorization endpoint.

    Permissions:
        AllowAny — public endpoint, no authentication required.

    Endpoints:
        GET /api/auth/google/
    """

    permission_classes = [AllowAny]
    throttle_classes = [OAuthRateThrottle]

    def get(self, request):
        """Redirect to Google authorization URL."""
        url = GoogleOAuthService().get_authorization_url(request)
        return redirect(url)


class GoogleCallbackView(APIView):
    """Handle the OAuth callback from Google.

    Validates the state parameter, exchanges the authorization code for
    tokens, validates the id_token, finds or creates the local User, then
    issues a short-lived single-use exchange code and redirects the frontend
    with it in the URL fragment. No JWT is ever placed in the URL (#43); the
    SPA redeems the code at POST /api/auth/google/exchange/.

    Permissions:
        AllowAny — called by Google's redirect, no prior auth.

    Endpoints:
        GET /api/auth/google/callback/
    """

    permission_classes = [AllowAny]
    throttle_classes = [OAuthRateThrottle]

    def get(self, request):
        """Process Google callback and redirect frontend with a single-use code."""
        code = request.GET.get("code")
        state = request.GET.get("state")

        if not code or not state:
            logger.warning("Google callback missing code or state params.")
            return redirect(f"{settings.FRONTEND_URL}/auth/error?reason=missing_params")

        service = GoogleOAuthService()
        try:
            user = service.handle_callback(request, code=code, state=state)
        except ValueError as exc:
            logger.warning("Google OAuth callback failed: %s", exc)
            return redirect(f"{settings.FRONTEND_URL}/auth/error?reason=oauth_failed")

        exchange_code = service.issue_exchange_code(user)

        # Single-use code in the fragment (#) — no JWT in the URL (#43). The SPA
        # redeems it immediately at the exchange endpoint for the token pair.
        return redirect(f"{settings.FRONTEND_URL}/auth/callback#code={exchange_code}")


class GoogleTokenExchangeView(APIView):
    """Exchange a single-use OAuth code for a JWT pair (#43).

    The Google callback hands the browser an opaque, short-lived code instead
    of the tokens themselves; the SPA immediately POSTs it here to receive the
    access/refresh pair in the response body — keeping JWTs out of the URL.

    Permissions:
        AllowAny — the single-use code itself authenticates the exchange.

    Authentication:
        None — runs no JWT authentication, so a stale/expired Authorization
        header attached by the SPA's HTTP client cannot 401 a valid exchange
        (the global JWTAuthentication would otherwise reject it before the
        AllowAny permission is reached) (#43).

    Endpoints:
        POST /api/auth/google/exchange/
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [OAuthRateThrottle]

    def post(self, request):
        """Redeem the code and return the JWT pair in the body."""
        code = request.data.get("code")
        user = GoogleOAuthService().consume_exchange_code(code)

        if user is None:
            logger.warning("Google token exchange failed: invalid or expired code.")
            return Response(
                {"detail": "Invalid or expired authorization code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh)},
            status=status.HTTP_200_OK,
        )
