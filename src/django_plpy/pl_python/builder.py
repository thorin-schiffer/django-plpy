import inspect
import json
from distutils.sysconfig import get_python_lib
from functools import wraps
from textwrap import dedent
from typing import Dict, List

from django.conf import settings
from django.db import connection

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
    start = source_code.find(f"@{name}")
    end = source_code.find("def")
    if start < 0:
        return source_code
    return source_code[:start] + source_code[end:]


def build_pl_function(f):
    name = f.__name__
    signature = inspect.signature(f)
    try:
        pl_args = []
        python_args = []
        for arg, specs in signature.parameters.items():
            if specs.annotation not in type_mapper:
                raise RuntimeError(f"Unknown type {specs.annotation}")
            pl_args.append(f"{arg} {type_mapper[specs.annotation]}")
            if specs.annotation == Dict[str, str]:
                python_args.append(f"json.loads({arg})")
            else:
                python_args.append(arg)
    except KeyError as ex:
        raise RuntimeError(f"{ex}:"
                           f"Function {f} must be fully annotated to be translated to pl/python")

    header = f"CREATE OR REPLACE FUNCTION {name} ({','.join(pl_args)}) RETURNS {type_mapper[signature.return_annotation]}"

    body = remove_decorator(inspect.getsource(f), "plfunction")
    return f"""{header}
AS $$
from typing import Dict, List
import json
{dedent(body)}
return {name}({','.join(python_args)})
$$ LANGUAGE plpython3u
"""


def build_pl_trigger_function(f, event, when, table=None, model=None):
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
        back_convert_statement = f"""
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


def install_function(f, trigger_params=None):
    trigger_params = trigger_params or {}
    pl_python_function = build_pl_trigger_function(f, **trigger_params) if trigger_params else build_pl_function(f)
    with connection.cursor() as cursor:
        cursor.execute(pl_python_function)


pl_functions = {}
pl_triggers = {}


def plfunction(f):
    @wraps(f)
    def installed_func(*args, **kwargs):
        return f(*args, **kwargs)

    module = inspect.getmodule(installed_func)
    pl_functions[f"{module.__name__}.{installed_func.__qualname__}"] = installed_func
    return installed_func


def pltrigger(**trigger_parameters):
    def _pl_trigger(f):
        @wraps(f)
        def installed_func(*args, **kwargs):
            return f(*args, **kwargs)

        module = inspect.getmodule(installed_func)
        pl_triggers[f"{module.__name__}.{installed_func.__qualname__}"] = installed_func, trigger_parameters
        return installed_func

    return _pl_trigger


@plfunction
def pl_load_path(path: str):
    import sys
    sys.path.append(path)


def load_path(path):
    install_function(pl_load_path)
    with connection.cursor() as cursor:
        cursor.execute(f"select pl_load_path('{path}')")


def load_env():
    """
    Installs and loads the virtualenv of this project into the postgres interpreter.
    """
    load_path(get_python_lib())


def load_project(path=None):
    install_function(pl_load_path)
    path = path or settings.BASE_DIR
    load_path(path)


@plfunction
def pl_load_django(project_dir: str, django_settings_module: str, extra_env: Dict[str, str]):
    import os, sys
    os.environ.update(**extra_env)
    from django.core.wsgi import get_wsgi_application
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', django_settings_module)
    sys.path.append(project_dir)
    get_wsgi_application()


def load_django(setting_module, project_path=None, extra_env=None):
    load_env()
    load_project(project_path)
    install_function(pl_load_django)
    extra_env = extra_env or {}

    with connection.cursor() as cursor:
        cursor.execute(f"select pl_load_django('{project_path}', '{setting_module}', "
                       f"'{json.dumps(extra_env)}')")


@plfunction
def pl_python_version() -> str:
    from platform import python_version
    return python_version()


def get_python_info():
    install_function(pl_python_version)
    with connection.cursor() as cursor:
        cursor.execute(f"select pl_python_version()")
        info = {
            'version': cursor.fetchone()[0]
        }
    return info
