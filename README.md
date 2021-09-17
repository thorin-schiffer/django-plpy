Django utilities for Postgres PL/Python.

[![Maintainability](https://api.codeclimate.com/v1/badges/8fe31e70125f34ad5328/maintainability)](https://codeclimate.com/github/eviltnan/django-plpy/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/8fe31e70125f34ad5328/test_coverage)](https://codeclimate.com/github/eviltnan/django-plpy/test_coverage)
[![test](https://github.com/eviltnan/django-plpy/actions/workflows/test.yml/badge.svg)](https://github.com/eviltnan/django-plpy/actions/workflows/test.yml)
[![lint](https://github.com/eviltnan/django-plpy/actions/workflows/lint.yml/badge.svg)](https://github.com/eviltnan/django-plpy/actions/workflows/lint.yml)

## What is django-plpy

PostgreSQL's PL/Python plugin allows you to write stored procedures in Python. Django-plpy provides utilities and
commands for using python functions from your project within Django ORM and more.

## Requirements

Django 2.2 or later, Python 3.6 or higher, Postgres 10 or higher.

### Installation

PL/Python therefore django-plpy requires postgres plugin for plpython3u. Most of the distributions provide it in their
repositories, here is how you install it on ubuntu:

```
apt-get -y install postgresql-plpython3-10
```

mind the PostgreSQL version at the end.

Install django-plpy with pip

```
pip install django-plpy
```

Add it to INSTALLED_APPS

```python
INSTALLED_APPS = [
    ...,
    "django_plpy",
    ...,
]
```

Migrate

```
./manage.py migrate
```

Check if your local python environment is compatible with your Postgres python interpreter.

```shell
./manage.py checkenv
```

Django-plpy is ready to be used.

## Usage

### Installing of python functions

The main workflow for bringing python functions to the database is to decorate them with
`@plpython` and call manage.py command `syncfunctions` in order to install them. Full annotation is needed for the
proper arguments mapping to the corresponding postgres type function signature. Currently supported types are:

```
    int: "integer",
    str: "varchar",
    inspect._empty: "void",
    Dict[str, str]: "JSONB",
    List[str]: "varchar[]",
    List[int]: "int[]",
    bool: "boolean",
    float: "real",
```

Imagine a function like this:

```python

from django_plpy.installer import plfunction


@plfunction
def pl_max(a: int, b: int) -> int:
    if a > b:
        return a
    return b
```

finding a maximum of two values. @plfunction decorator registers it for installation, if any function with that name
already exists it will be overwritten. Call `syncfunctions` command to install it into the database:

```
./manage.py syncfynctions
```

Now you can use it in your SQL quieries:

```python
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("select pl_max(10, 20)")
    row = cursor.fetchone()
assert row[0] == 20
```

Or even use as a custom function in the django ORM:

```python
from django.db.models import F, Func
from tests.books.models import Book

Book.objects.annotate(
    max_value=Func(F("amount_sold"), F("amount_stock"), function="pl_max")
)
```

or even declared as a custom ORM lookup:

```python
from django_plpy.installer import plfunction
from django.db.models import Transform
from django.db.models import IntegerField
from tests.books.models import Book


@plfunction
def plsquare(a: int) -> int:
    return a * a


class PySquare(Transform):
    lookup_name = "plsquare"
    function = "plsquare"


IntegerField.register_lookup(PySquare)
assert Book.objects.filter(amount_stock__plsquare=400).exists()
```

### Installing of python triggers

Triggers are a very mighty mechanism, django-plpy allows you to easily mark python function as a trigger, so some logic
from your project is directly associated with the data changing events in the database.

Here is an example of a python trigger using the `@pltrigger` decorator.

```python

from django_plpy.installer import pltrigger


@pltrigger(event="INSERT", when="BEFORE", table="books_book")
def pl_trigger(td, plpy):
    # mind triggers don't return anything
    td["new"]["name"] = td["new"]["name"] + "test"
    td["new"]["amount_sold"] = plpy.execute("SELECT count(*) FROM books_book")[0][
        "count"
    ]
```

The parameters of `@pltrigger` decorator declare the trigger parameters like event the trigger will bind to and table
name. You can replace `table_name` with a model name, the table name will looked up automatically:

```python

from django_plpy.installer import pltrigger
from django.db.models import Model, CharField, IntegerField


class Book(Model):
    name = CharField(max_length=10)
    amount_stock = IntegerField(default=20)
    amount_sold = IntegerField(default=10)


@pltrigger(event="INSERT", when="BEFORE", model=Book)
def pl_trigger(td, plpy):
    # mind triggers don't return anything
    td["new"]["name"] = td["new"]["name"] + "test"
    td["new"]["amount_sold"] = plpy.execute("SELECT count(*) FROM books_book")[0][
        "count"
    ]
```

Read more about plpy triggers in the official postgres
documentation: https://www.postgresql.org/docs/13/plpython-database.html.

### manage.py commands

```syncfunctions``` installs functions and triggers decorated with `@plfunction` and `@pltrigger` to the database.

```shell
(venv) thorin@thorin-N141CU:~/PycharmProjects/django-plpy$ ./manage.py syncfunctions
Synced 4 functions and 1 triggers
```

```checkenv``` checks if your local python and database's python versions are compatible.

```shell
(venv) thorin@thorin-N141CU:~/PycharmProjects/django-plpy$ ./manage.py checkenv
Database's Python version: 3.7.3
Minor versions match, local version: 3.7.12. Django-plpy Django ORM can be used in triggers.
```

If your local python and database's python versions have different minor releases, psycopg won't work, so django ORM
cannot be used in triggers. This is what you will see in this case:

```shell
(venv) thorin@thorin-N141CU:~/PycharmProjects/django-plpy$ ./manage.py checkenv
Database's Python version: 3.6.9
Postgres python and this python's versions don't match, local version: 3.7.12.Django-plpy Django ORM cannot be used in triggers.
```

### Using Django in PL functions and triggers

While installing with `syncfunctions` the source code of the function will be copied to a corresponding stored procedure
and installed in postgres. This makes your local context not available to the functions, which means that no models or
libraries can be used within the tranferred functions.

In order to solve this problem, you need to set up your python project and environment within a postgres python
interpreter. Django-plpy supports following two scenarios of how you use your database.

#### Database and application are on the same host

Rarely used nowadays, but still out there, this scenario is the simplest for the environment sharing. Django-plpy
creates stored procedures and transfers the necessary configuration to the database:

- secrets and database access creds
- path to the python env (defaults to `distutils.sysconfig.get_python_lib()`, for more config see below)
- loads django applications the way manage.py does it

#### Database is in a separate docker container

More common production scenario is that the database is on a separate docker container.

##### Couple of words about docker and plpython or django-plpy

Official Postgres image doesn't support plpython plugin out of the box, so if you want to use plpython as such you would
need to create your own image or use one of those provided by the maintainer of this package (
thorinschiffer/postgres-plpython:<your postgres version>).

All of the images provide python 3.7, because postgres uses the default python environment from the OS the image is
based on and 3.7 is the standard for Debian Buster.

##### Using django-plpy with dockerized Postgres

To make the code available to the Postgres python interpreter, it has to somehow appear within the docker container. You
can either provision the image with it while building if you decided to write your own docker image / dockerfile or you
can share the code using volumes.

Once the code and environment exist somewhere within the Docker container, django-plpy can be told to use them:
So if your environment lives under `/env` (copy site-packages folder to this path) and your app within `/app`, add
following settings to your `settings.py`

```python
PLPY_ENV_PATHS = ["/env"]
PLPY_PROJECT_PATH = "/app"
```

##### Loading env

TODO: need command

##### Loading django project and using ORM in functions and triggers

##### Loading your project and using it in functions and triggers

+ settings PLPY_
+ install command
+ trigger (https://django-pgtrigger.readthedocs.io/en/latest/tutorial.html#keeping-a-field-in-sync-with-another)
+ use python function in the bulk update function
+ install function with TD
+ load virtualenv
+ load project
+ access ORM within function
+ some functions for django lookups
+ manage py commands
+ mind the python versions, official postgres10 is based on stretch by default which only has 3.5
+ it's easier to update python version in your env then change the python version in plpython (would need to rebuild
  from source)
+ in docker images python 3.7.3 was used, because it's a system version for buster

## Under the hood

- considering AWS RDS
- about python versions in postgres
- how the code is installed
- often django beginners misunderstand signals concept
- add sorting example with a custom python function
- plpy example for triggers
- if you see `Error loading psycopg2 module: No module named 'psycopg2._psycopg'`, your local python and db's versions
  don't match
- including ORM will only work when django project is on the same host, which is rare. the only real way is to install
  the whole code on the db host
- there is certain danger of getting them out of hand
- provision custom postgres container with plpythonu and your code so ORM is accessible
- if you see this:

```
django.db.utils.ProgrammingError: language "plpython3u" does not exist
HINT:  Use CREATE LANGUAGE to load the language into the database.
```

you haven't migrated

- python versions is a mess in debian, use pyenv in docker images for plpython?
- environment / interpreter context persistence and database restart
- start database functions with plpy_ prefix to be sure they are not executed locally

## contribution

## Installation for development

Install project locally: `pip install -e .`

Django-plpy [django-environ](https://github.com/joke2k/django-environ) for passing the necessary env over dotenv,
database for creds in particular. See .env_template for possible env variables.
