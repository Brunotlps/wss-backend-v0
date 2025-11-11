"""
Django Admin configuration for Users app
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _ 

from .models import User, Profile

@admin.register(User)
class UserAdmin(BaseUserAdmin):

  list_display = ('email', 'username', 'first_name', 'last_name', 'is_instructor', 'is_staff', 'date_joined')
  list_filter = ('is_instructor', 'is_staff', 'is_superuser', 'is_active', 'date_joined')
  search_fields = ('email', 'username', 'first_name', 'last_name', 'phone')
  ordering = ('-date_joined',)

  # Organize fields in sections
  fieldsets = (
    (None, {'fields': ('email', 'username', 'password')}),
    (_('Personal info'), {'fields': ('first_name', 'last_name', 'phone')}),
    (_('Permissions'), {
        'fields': ('is_active', 'is_staff', 'is_superuser', 'is_instructor', 'groups', 'user_permissions'),
    }),
    (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
  )

  # Fields shown when creating new user
  add_fieldsets = (
    (None, {
        'classes': ('wide',),
        'fields': ('email', 'username', 'password1', 'password2', 'is_instructor'),
    }),    
  )

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):

  list_display = ('user', 'birth_date', 'created_at')
  list_filter = ('created_at',)
  search_fields = ('user__email', 'user__username', 'bio')
  readonly_fields = ('created_at', 'updated_at')
  
  fieldsets = (
      (_('User'), {'fields': ('user',)}),
      (_('Personal Information'), {
          'fields': ('bio', 'avatar', 'birth_date')
      }),
      (_('Social Links'), {
          'fields': ('website', 'linkedin', 'instagram'),
          'classes': ('collapse',)  # Collapsed by default
      }),
      (_('Timestamps'), {
          'fields': ('created_at', 'updated_at'),
          'classes': ('collapse',)
      }),
  )