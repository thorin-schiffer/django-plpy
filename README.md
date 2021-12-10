# README

Django utilities for Postgres PL/Python. WIP

[![Maintainability](https://api.codeclimate.com/v1/badges/8fe31e70125f34ad5328/maintainability)](https://codeclimate.com/github/eviltnan/django-plpy/maintainability) [![Test Coverage](https://api.codeclimate.com/v1/badges/8fe31e70125f34ad5328/test\_coverage)](https://codeclimate.com/github/eviltnan/django-plpy/test\_coverage) [![test](https://github.com/eviltnan/django-plpy/actions/workflows/test.yml/badge.svg)](https://github.com/eviltnan/django-plpy/actions/workflows/test.yml) [![lint](https://github.com/eviltnan/django-plpy/actions/workflows/lint.yml/badge.svg)](https://github.com/eviltnan/django-plpy/actions/workflows/lint.yml)

### What is django-plpy

PostgreSQL's PL/Python plugin allows you to write stored procedures in Python. Django-plpy provides utilities and commands for using python functions from your project within Django ORM and more.

### Requirements

Django 2.2 or later, Python 3.6 or higher, Postgres 10 or higher.

#### Installation

PL/Python, therefore django-plpy requires Postgres plugin for plpython3u. Most of the distributions provide it in their repositories, here is how you install it on Ubuntu:

```
apt-get -y install postgresql-plpython3-10
```

Mind the PostgreSQL version at the end.

Install django-plpy with pip

```
pip install django-plpy
```

Add it to INSTALLED\_APPS

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

### Features

#### Installing of python functions

The main workflow for bringing python functions to the database is to decorate them with `@plpython` and call manage.py command `syncfunctions` to install them. Full annotation is needed for the proper arguments mapping to the corresponding Postgres type function signature.&#x20;

Imagine a function like this:

```python
from django_plpy.installer import plfunction


@plfunction
def pl_max(a: int, b: int) -> int:
    if a > b:
        return a
    return b
```

Finding a maximum of two values. @plfunction decorator registers it for installation, if any function with that name already exists it will be overwritten. Call `syncfunctions` command to install it into the database:

```
./manage.py syncfynctions
```

#### Python functions in SQL queries

```python
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("select pl_max(10, 20)")
    row = cursor.fetchone()
assert row[0] == 20
```

#### Python functions in annotations

```python
from django.db.models import F, Func
from tests.books.models import Book

Book.objects.annotate(
    max_value=Func(F("amount_sold"), F("amount_stock"), function="pl_max")
)
```

#### Using python functions for custom ORM lookups

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

#### Installing of python triggers

Triggers are a very mighty mechanism, django-plpy allows you to easily mark a python function as a trigger, so some logic from your project is directly associated with the data changing events in the database.

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

#### Using Django models in triggers

The parameters of `@pltrigger` decorator declare the trigger parameters like event the trigger will bind to and table name. You can replace `table_name` with a model name, the table name will looked up automatically:

```python
from django_plpy.installer import pltrigger
from django.db.models import Model, CharField, IntegerField


class Book(Model):
    name = CharField(max_length=10)
    amount_stock = IntegerField(default=20)
    amount_sold = IntegerField(default=10)


@pltrigger(event="INSERT", when="BEFORE", model=Book)
def pl_update_amount(new: Book, old: Book, td, plpy):
    # don't use save method here, it will kill the database because of recursion
    new.amount_stock += 10
```

Read more about plpy triggers in the official Postgres documentation: https://www.postgresql.org/docs/13/plpython-database.html.

Using Django models in triggers comes at a price, read about the details of implementation below.

#### Bulk operations and triggers, migrations

Python triggers are fully featured Postgres triggers, meaning they will be created for every row, unlike Django signals. So if you define a trigger with event="UPDATE" and call a bulk update on a model, the trigger will be called for all affected by the operation:

```python
from django_plpy.installer import pltrigger
from tests.books.models import Book


@pltrigger(event="UPDATE", when="BEFORE", model=Book)
def pl_update_amount(new: Book, old: Book, td, plpy):
    # don't use save method here, it will kill the database because of recursion
    new.amount_stock += 10
```

Update results a trigger call on every line:

```python
from tests.books.models import Book

Book.objects.values('amount_stock')
# <QuerySet [{'amount_stock': 30}, {'amount_stock': 30}, {'amount_stock': 30}]>

Book.objects.all().update(name="test")
# 3

Book.objects.values('amount_stock')
# <QuerySet [{'amount_stock': 40}, {'amount_stock': 40}, {'amount_stock': 40}]>
```

Unlike the code of Django models or signals, triggers will also be called while migrations.

#### Turning Django signals to python triggers

Although Django signals are neither asynchronous nor have any ability to be executed in another thread or process, many developers mistakenly expect them to behave this way. Often it leads to a callback hell and complex execution flow. Django signals implement a dispatcher-receiver pattern and only make an impression of asynchronous execution.

With django-plpy, you can quickly turn your signals into triggers and make them truly asynchronous.

Before:

```python
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.auth.models import User


@receiver(post_save, sender=User)
def send_mail(sender, instance, **kwargs):
    instance.send_mail()
```

After:

```python
from django_plpy.installer import pltrigger
from django.contrib.auth.models import User


@pltrigger(event="INSERT", when="AFTER", model=User)
def pl_send_mail(new: User, old: User, td, plpy):
    new.send_mail()
```

#### Manage.py commands

`syncfunctions` installs functions and triggers decorated with `@plfunction` and `@pltrigger` to the database.

```shell
(venv) thorin@thorin-N141CU:~/PycharmProjects/django-plpy$ ./manage.py syncfunctions
Synced 4 functions and 1 triggers
```

`checkenv` checks if your local python and database's python versions are compatible.

```shell
(venv) thorin@thorin-N141CU:~/PycharmProjects/django-plpy$ ./manage.py checkenv
Database's Python version: 3.7.3
Minor versions match, local version: 3.7.12. Django-plpy Django ORM can be used in triggers.
```

If your local python and database's python versions have different minor releases, psycopg won't work, so Django ORM cannot be used in triggers. This is what you will see in this case:

```shell
(venv) thorin@thorin-N141CU:~/PycharmProjects/django-plpy$ ./manage.py checkenv
Database's Python version: 3.6.9
Postgres python and this python's versions don't match, local version: 3.7.12.Django-plpy Django ORM cannot be used in triggers.
```

### Under the hood

#### Supported argument types

Currently, supported types are:

```
int: "integer",
str: "varchar",
Dict[str, str]: "JSONB",
List[str]: "varchar[]",
List[int]: "int[]",
bool: "boolean",
float: "real",
```

#### Using Django in PL functions and triggers

While installing with, `syncfunctions` the source code of the function will be copied to a corresponding stored procedure and installed in Postgres. This makes your local context not available to the functions, which means that no models or libraries can be used within the transferred functions.

To solve this problem, you need to set up your python project and environment within a Postgres python interpreter. Django-plpy supports the following two scenarios of how you use your database.

**Database and application are on the same host**

Rarely used nowadays, but still out there, this scenario is the simplest for the environment sharing. Django-plpy creates stored procedures and transfers the necessary configuration to the database:

* secrets and database access credentials
* path to the python env (defaults to `distutils.sysconfig.get_python_lib()`, for more config see below)
* loads Django applications the way manage.py does it

**Database is in a separate docker container**

A more common production scenario is that the database is on a separate docker container.

**Couple of words about docker and plpython or django-plpy**

The official Postgres image doesn't support plpython plugin out of the box, so if you want to use plpython as such you would need to create your image or use one of those provided by the maintainer of this package (thorinschiffer/postgres-plpython).

All the images provide python 3.7 because Postgres uses the default python environment from the OS the image is based on and 3.7 is the standard for Debian Buster.

**Using django-plpy with dockerized Postgres**

To make the code available to the Postgres python interpreter, it has to somehow appear within the docker container. You can either provision the image with it while building if you decided to write your docker image / dockerfile, or you can share the code using volumes.

Once the code and environment exist somewhere within the Docker container, django-plpy can be told to use them: So if your environment lives under `/env` (copy site-packages folder to this path) and your app within `/app`, add following settings to your `settings.py`

```python
PLPY_ENV_PATHS = ["/env"]
PLPY_PROJECT_PATH = "/app"
```

#### AWS RDS and other managed databases

In the times of Saas there databases are rarely connected in a docker image but much
more frequently in a managed database like AWS RDS.
Django-plpy can be only install simple functions and triggers in such instances, because
there is no access to the database's filesystem in such setup.

Besides that some managed databases won't give you superuser rights, meaning installing
extensions in such a scenario will be troublesome.


#### How the code is installed

Django-plpy copies the function code, wraps it in a PL/Python stored procedure or trigger
and then installs it with `manage.py syncfunctions`.
If you use Django models, database has to have access to your project file and virtualenv (see above),
or if you create your own database docker image, it has to be provisioned correspondingly.
This scenario seems quite exotic, and you do it on your own risk.

#### Troubleshooting

If you see `Error loading psycopg2 module: No module named 'psycopg2._psycopg'`, your local python and db's versions don't match.
Check your python versions with `manage.py checkenv`

If you see this:

```
django.db.utils.ProgrammingError: language "plpython3u" does not exist
HINT:  Use CREATE LANGUAGE to load the language into the database.
```

you haven't migrated: `manage.py migrate`
#### Caveats

Custom functions and triggers are not a part of Django ORM and can get out of hand, name collisions are not checked explicitely for now.

For now enabling orm stores the os.environ in json in plaintext in the trigger function text, so this feature is
considered quite experimental.

There were no real performance tests made, so this is for you to find out.
Currently only python3.7 is supported with Django ORM, as it is a current version in the Debian based python images,
that are default. There is an opportunity to build an image with a custom python verson and postgres version, but
it seems a total overkill assuming all the problems with Django ORM, see above.

Prepend database functions with plpy_ prefix to be sure they are not executed locally.
Django-plpy won't remove any triggers, you will have to take care of the stale triggers yourself.

### Installation for development

Install project locally: `pip install -e .`

Django-plpy [django-environ](https://github.com/joke2k/django-environ) for passing the necessary env over dotenv, database for creds in particular. See .env\_template for possible env variables.

### Changelog

#### 0.1.0 Initial release

- pl functions
- pl triggers
