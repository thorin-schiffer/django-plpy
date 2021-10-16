__author__ = "Thorin Schiffer"

import inspect
import json
from functools import wraps
from typing import Dict

from django.db import connection
from django_plpy.builder import build_pl_trigger_function, build_pl_function
from django_plpy.settings import ENV_PATHS, PROJECT_PATH


def install_function(f, trigger_params=None, function_params=None, cursor=None):
    """
    Installs function f as a trigger or stored procedure to the database. Must have a proper signature:
    - td, plpy for trigger without django ORM
    - new: Model, old: Model, td, plpy for trigger with django ORM
    Stored procedure arguments must be type annotated for proper type mapping to PL/SQL built in types.
    Read more about td https://www.postgresql.org/docs/13/plpython-trigger.html
    and plpy https://www.postgresql.org/docs/13/plpython-database.html objects
    @param f: function/callable to install as
    @param trigger_params: dict with params as accepted by build_pl_trigger_function
    """
    trigger_params = trigger_params or {}
    function_params = function_params or {}
    print(f)
    pl_python_function = (
        build_pl_trigger_function(f, **trigger_params)
        if trigger_params
        else build_pl_function(f, **function_params)
    )
    if not cursor:
        with connection.cursor() as cursor:
            cursor.execute(pl_python_function)
    else:
        cursor.execute(pl_python_function)


pl_functions = {}
pl_triggers = {}


def plfunction(*args, **parameters):
    """
    Decorator marking a function for installation with manage.py syncfunctions as a stored procedure
    @param parameters: parameters. global_ - makes the function available to other plpy functons over GD dict
    @return: wrapped registered function
    """

    def _plfunction(f):
        @wraps(f)
        def installed_func(*args, **kwargs):
            return f(*args, **kwargs)

        module = inspect.getmodule(installed_func)
        pl_functions[f"{module.__name__}.{installed_func.__qualname__}"] = (
            installed_func,
            parameters,
        )
        return installed_func

    return _plfunction(args[0]) if args and callable(args[0]) else _plfunction


def pltrigger(**trigger_parameters):
    """
    Decorator marking a function for installation with manage.py syncfunctions as a trigger function, see
    build_pl_trigger_function for parameters
    @param trigger_parameters: params of the trigger
    @return: wrapped registered function
    """

    def _pl_trigger(f):
        @wraps(f)
        def installed_func(*args, **kwargs):
            return f(*args, **kwargs)

        module = inspect.getmodule(installed_func)
        pl_triggers[f"{module.__name__}.{installed_func.__qualname__}"] = (
            installed_func,
            trigger_parameters,
        )
        return installed_func

    return _pl_trigger


@plfunction
def pl_load_path(path: str):  # pragma: no cover
    """
    Loads function path on the file system to database interpreter
    @param path: path on the database's filesystem
    """
    import sys

    sys.path.append(path)


def load_path(path):
    """
    Loads local path to the database's interpreter. Will only work if the database and application are on the same host.
    @param path: local system filepath to load
    """
    install_function(pl_load_path)
    with connection.cursor() as cursor:
        cursor.execute(f"select pl_load_path('{path}')")


def load_env():
    """
    Installs and loads the virtualenv of this project into the postgres interpreter.
    """
    raise NotImplementedError("fail on loading of an empty path")
    for path in ENV_PATHS:
        load_path(path)


def load_project(path=None):
    """
    Load application to the database interpreter by path from PLPY_PROJECT_PATH setting. Defaults to BASE_DIR.parent.
    @param path: path of the project, defaults to PLPY_PROJECT_PATH
    """
    install_function(pl_load_path)
    path = path or PROJECT_PATH
    load_path(path)


# this code is only run in the database interpreter, that's why coverage doesn't see it
@plfunction
def pl_load_django(
    project_dir: str, django_settings_module: str, extra_env: Dict[str, str]
):  # pragma: no cover
    """
    Stored procedure to configure django application in the context of the database interpreter.
    @param project_dir: project path
    @param django_settings_module: name of the django settings module to use
    @param extra_env: extra environment to pass to the database interpreter, like secrets
    """
    import os
    import sys

    os.environ.update(**extra_env)
    from django.core.wsgi import get_wsgi_application

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", django_settings_module)
    sys.path.append(project_dir)
    get_wsgi_application()


def load_django(setting_module, project_path=None, extra_env=None):
    """
    Loads django to the database interpreter.
    @param project_dir: project path
    @param django_settings_module: name of the django settings module to use
    @param extra_env: extra environment to pass to the database interpreter, like secrets
    """
    load_env()
    load_project(project_path)
    install_function(pl_load_django)
    extra_env = extra_env or {}

    with connection.cursor() as cursor:
        cursor.execute(
            f"select pl_load_django('{project_path}', '{setting_module}', "
            f"'{json.dumps(extra_env)}')"
        )


def sync_functions():
    """
    Installs functions decorated with @plfunction and @pltrigger to the database
    """
    for function_name, f in pl_functions.items():
        install_function(f[0], function_params=f[1])

    for function_name, f in pl_triggers.items():
        install_function(f[0], trigger_params=f[1])


@plfunction
def pl_python_version() -> str:  # pragma: no cover
    """
    Stored procedure that returns databases python interpreter version
    @return: semantic python version X.X.X
    """
    from platform import python_version

    return python_version()


def get_python_info():
    """
    Return database python info as a dict
    @return: dict with python information
    """
    install_function(pl_python_version)
    with connection.cursor() as cursor:
        cursor.execute("select pl_python_version()")
        info = {"version": cursor.fetchone()[0]}
    return info
