import inspect
import json
from functools import wraps
from textwrap import dedent
from typing import Dict, List

from django.db import connection
from django_plpy.settings import ENV_PATHS, PROJECT_PATH

type_mapper = {
    int: "integer",
    str: "varchar",
    inspect._empty: "void",
    Dict[str, str]: "JSONB",
    List[str]: "varchar[]",
    List[int]: "int[]",
    bool: "boolean",
    float: "real",
}


def remove_decorator(source_code, name):
    """
    Removes decorator with the name from the source code

    @param source_code: code of the function as returned by inspect module
    @param name: name of the decorator to remove
    @return: source code of the function without the decorator statement
    """
    start = source_code.find(f"@{name}")
    end = source_code.find("def")
    if start < 0:
        return source_code
    return source_code[:start] + source_code[end:]


def build_pl_function(f) -> str:
    """
    Builds the source code of the plpy stored procedure from the local python code.
    The function code gets copied and installed to the database.
    Use syncfunctions manage.py command to install the functions to the database
    @param f: function / callable the code of will be rendered to the plpy stored procedure
    @return: the code of the stored procedure
    """
    name = f.__name__
    signature = inspect.signature(f)
    pl_args = []
    python_args = []
    for arg, specs in signature.parameters.items():
        if specs.annotation is inspect._empty:
            raise RuntimeError(
                f"Function {f} must be fully annotated to be translated to pl/python"
            )
        if specs.annotation not in type_mapper:
            raise RuntimeError(f"Unknown type {specs.annotation}")
        pl_args.append(f"{arg} {type_mapper[specs.annotation]}")
        if specs.annotation == Dict[str, str]:
            python_args.append(f"json.loads({arg})")
        else:
            python_args.append(arg)

    header = (
        f"CREATE OR REPLACE FUNCTION {name} ({','.join(pl_args)}) "
        f"RETURNS {type_mapper[signature.return_annotation]}"
    )

    body = remove_decorator(inspect.getsource(f), "plfunction")
    return f"""{header}
AS $$
from typing import Dict, List
import json
{dedent(body)}
return {name}({','.join(python_args)})
$$ LANGUAGE plpython3u
"""


def build_pl_trigger_function(f, event, when, table=None, model=None) -> str:
    """
    Builds source code of the trigger function from the python function f.
    The source code will be copied to the trigger function and installed in the database.
    Use syncfunctions manage.py command to install the function within the database.
    Read more about plpy trigger functions here https://www.postgresql.org/docs/13/plpython-trigger.html
    @param f: function/callable
    @param event: contains the event as a string: INSERT, UPDATE, DELETE, or TRUNCATE
    @param when: contains one of BEFORE, AFTER, or INSTEAD OF
    @param table: table name the trigger will be installed on, incompatible with model argument
    @param model: django model name the trigger is to be associated with, incompatible with tabel argument
    @return: source code of the trigger function
    """
    if not table and not model:
        raise RuntimeError("Either model or table must be set for trigger installation")

    name = f.__name__
    if model:
        meta = model.objects.model._meta
        table = meta.db_table
        model_name = meta.object_name
        app_name = meta.app_label
        import_statement = f"""
from django.apps import apps
from django.forms.models import model_to_dict

{model_name} = apps.get_model('{app_name}', '{model_name}')
new = {model_name}(**TD['new'])
old = {model_name}(**TD['old']) if TD['old'] else None
"""
        call_statement = f"{name}(new, old, TD, plpy)"
        back_convert_statement = """
TD['new'].update(model_to_dict(new))
if TD['old']:
    TD['old'].update(model_to_dict(old))
"""
    else:
        import_statement = back_convert_statement = ""
        call_statement = f"{name}(TD, plpy)"

    header = f"CREATE OR REPLACE FUNCTION {name}() RETURNS TRIGGER"

    body = remove_decorator(inspect.getsource(f), "pltrigger")
    return f"""
BEGIN;
{header}
AS $$
{import_statement}
{dedent(body)}
{call_statement}
{back_convert_statement}
return 'MODIFY'
$$ LANGUAGE plpython3u;

DROP TRIGGER IF EXISTS {name + '_trigger'} ON {table} CASCADE;
CREATE TRIGGER {name + '_trigger'}
{when} {event} ON {table}
FOR EACH ROW
EXECUTE PROCEDURE {name}();
END;
"""


def install_function(f, trigger_params=None, cursor=None):
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
    pl_python_function = (
        build_pl_trigger_function(f, **trigger_params)
        if trigger_params
        else build_pl_function(f)
    )
    if not cursor:
        with connection.cursor() as cursor:
            cursor.execute(pl_python_function)
    else:
        cursor.execute(pl_python_function)


pl_functions = {}
pl_triggers = {}


def plfunction(f):
    """
    Decorator marking a function for installation with manage.py syncfunctions as a stored procedure
    @param f: function to be installed
    @return: wrapped registered function
    """

    @wraps(f)
    def installed_func(*args, **kwargs):
        return f(*args, **kwargs)

    module = inspect.getmodule(installed_func)
    pl_functions[f"{module.__name__}.{installed_func.__qualname__}"] = installed_func
    return installed_func


def pltrigger(**trigger_parameters):
    """
    Decorator marking a function for installation with manage.py syncfunctions as a trigger function
    @param f: function to be installed
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


def sync_functions():
    """
    Installs functions decorated with @plfunction and @pltrigger to the database
    """
    for function_name, f in pl_functions.items():
        install_function(f)

    for function_name, f in pl_triggers.items():
        install_function(f[0], f[1])
