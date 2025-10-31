# When Django starts, it imports config
# By importing config, __init__.py is executed
# This initializes Celery automatically
# Allows using @shared_task in any app


from .celery import app as celery_app

__all__ = ('celery_app',)