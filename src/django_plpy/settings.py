try:
    from distutils.sysconfig import get_python_lib

    default_env_paths = [get_python_lib()]
except ImportError:
    default_env_paths = []

from django.conf import settings

# python environment accessible for the database, within the docker container
# if postgres runs within a docker container
# defaults to the local python lib for the case of no containers when all runs
# on the same machine
ENV_PATHS = getattr(settings, "PLPY_ENV_PATHS", None) or default_env_paths
PROJECT_PATH = getattr(settings, "PLPY_PROJECT_PATH", None) or settings.BASE_DIR.parent
