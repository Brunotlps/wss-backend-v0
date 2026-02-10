"""
URL configuration for the Users application.

This module defines URL patterns for user authentication, profile management,
and user operations. It integrates APIView-based endpoints for registration
and current user retrieval with ViewSet-based endpoints for CRUD operations
on users and profiles.

Routes:
    POST   /api/auth/register/            → UserRegistrationView
    GET    /api/users/me/                 → CurrentUserView
    PATCH  /api/users/me/                 → CurrentUserView
    POST   /api/auth/token/               → TokenObtainPairView (Login)
    POST   /api/auth/token/refresh/       → TokenRefreshView (Renovar)
    POST   /api/auth/token/blacklist/     → TokenBlacklistView (Logout)
    GET    /api/users/                    → UserViewSet.list
    POST   /api/users/                    → UserViewSet.register
    GET    /api/users/{pk}/               → UserViewSet.retrieve
    PUT    /api/users/{pk}/               → UserViewSet.update
    PATCH  /api/users/{pk}/               → UserViewSet.partial_update
    DELETE /api/users/{pk}/               → UserViewSet.destroy
    GET    /api/profiles/                 → ProfileViewSet.list
    POST   /api/profiles/                 → ProfileViewSet.create
    GET    /api/profiles/{pk}/            → ProfileViewSet.retrieve
    PUT    /api/profiles/{pk}/            → ProfileViewSet.update
    PATCH  /api/profiles/{pk}/            → ProfileViewSet.partial_update
    DELETE /api/profiles/{pk}/            → ProfileViewSet.destroy
"""


from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, ProfileViewSet, CurrentUserView, UserRegistrationView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'profiles', ProfileViewSet, basename='profile')

urlpatterns = [
    path('auth/register/', UserRegistrationView.as_view(), name='register'),
    path('users/me/', CurrentUserView.as_view(), name='current-user'),

    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),

    path('', include(router.urls)),
]

