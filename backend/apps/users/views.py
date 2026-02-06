"""
Views for the users module.

This module implements the API endpoints for:
- Registration of new users
- Authentication and logged-in user profile management
- Complete CRUD of users (with permissions)
- User profile management
"""

from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action

from .models import User, Profile
from .serializers import (
    UserRegistrationSerializer,
    UserDetailSerializer,
    UserUpdateSerializer,
    UserListSerializer,
    ProfileSerializer,
)
from .permissions import IsOwnerOrReadOnly


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
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
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
                Allowed fields: first_name, last_name, phone, is_instructor.
        
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
        - IsOwnerOrReadOnly: Anyone can read, only owner can edit
    """
    
    # Base configuration
    queryset = User.objects.all()
    permission_classes = [IsOwnerOrReadOnly]
    
    # Filters and search
    filterset_fields = ['is_instructor', 'is_active']
    search_fields = ['username', 'email']
    ordering_fields = ['username', 'date_joined']
    ordering = ['-date_joined']
    
    # Dynamic serializers
    def get_serializer_class(self):
        """
        Returns the appropriate serializer for each action.
        
        Returns:
            Serializer class based on self.action:
            - list: UserListSerializer (minimal fields)
            - retrieve: UserDetailSerializer (complete with nested)
            - update/partial_update: UserUpdateSerializer (editable fields)
            - default: UserDetailSerializer
        """
        if self.action == 'list':
            return UserListSerializer
        elif self.action == 'retrieve':
            return UserDetailSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserDetailSerializer


class ProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for complete profile management.
    
    Provides CRUD endpoints for user profiles with:
    - Paginated and filterable listing
    - Complete details with related user information
    - Updates with validations
    - Optimized queries with select_related
    
    Permissions:
        - IsOwnerOrReadOnly: Anyone can read, only owner can edit
    """
    
    # Base configuration
    queryset = Profile.objects.select_related('user')
    serializer_class = ProfileSerializer
    permission_classes = [IsOwnerOrReadOnly]
