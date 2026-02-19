# When Django starts, it imports config
# By importing config, __init__.py is executed
# This initializes Celery automatically
# Allows using @shared_task in any app

# TODO: Uncomment when Celery is installed (pip install celery)
# from .celery import app as celery_app
# __all__ = ('celery_app',)

__all__ = ()