from distutils.sysconfig import get_python_lib

from django.conf import settings

# python environment accessible for the database, within the docker container
# if postgres runs within a docker container
# defaults to the local python lib for the case of no containers when all runs
# on the same machine
ENV_PATHS = getattr(settings, "PLPY_ENV_PATHS", [get_python_lib()])
PROJECT_PATH = getattr(settings, "PLPY_PROJECT_PATH", settings.BASE_DIR)
