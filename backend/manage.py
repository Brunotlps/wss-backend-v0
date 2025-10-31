""""
 manage.py - Command-line utility for administrative tasks
 
 This file is the entry point for running various project management commands.
 Common use cases include:
 - Starting the development server
 - Running database migrations
 - Creating database tables
 - Running tests
 - Creating superuser accounts
 - Collecting static files
 """

import os 
import sys

def main():
  
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

