"""
Users application initialization.

This module ensures that the UsersConfig is loaded when the app starts,
which in turn triggers signal registration via the ready() method.
"""

default_app_config = 'apps.users.apps.UsersConfig'
