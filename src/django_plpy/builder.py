import inspect
from textwrap import dedent
from typing import Dict, List
import json
from django_plpy.settings import ENV_PATHS, PROJECT_PATH
from django_plpy.utils import remove_decorator
from django.conf import settings

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


def build_pl_function(f, global_=False) -> str:
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
{"GD['{name}'] = {name}" if global_ else ""}
$$ LANGUAGE plpython3u
"""


def build_pl_trigger_function(
    f, event, when, table=None, model=None, extra_env=None
) -> str:
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
    @param extra_env: extra environment to be passed to the pl_enable_orm function, will be dumped plaintext in the
    text of the function!
    @return: source code of the trigger function
    """
    extra_env = extra_env or {}
    if not table and not model:
        raise RuntimeError("Either model or table must be set for trigger installation")

    name = f.__name__
    if model:
        meta = model.objects.model._meta
        table = meta.db_table
        model_name = meta.object_name
        app_name = meta.app_label
        import_statement = f"""
extra_env = '{json.dumps(extra_env)}'
plpy.execute(
    "select pl_enable_orm(array{ENV_PATHS}, '{PROJECT_PATH}', '{settings.SETTINGS_MODULE}', '%s')" % extra_env
)
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
