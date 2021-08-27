# django-plpy

Django utilities for Postgres PL/Python. Work in progress

## Description


### Installation
- python 3.6 minimum
- postgres 10 and postgresql-plpython3

- add django-plpy to INSTALLED_APPS
- migrate
## Usage
+ install simple python function
+ supported arguments types
+ settings PLPY_
+ install command
+ trigger (https://django-pgtrigger.readthedocs.io/en/latest/tutorial.html#keeping-a-field-in-sync-with-another)
+ install function with TD
+ load virtualenv
+ load project
+ access ORM within function
+ some functions for django lookups
+ manage py commands
+ mind the python versions, official postgres10 is based on stretch by default which only has 3.5
+ it's easier to update python version in your env then change the python version in plpython (would need to rebuild from source)

versions
10 - 3.5.3
11 - 3.7.3


## Under the hood

- about python versions in postgres
- how the code is installed
- often django beginners misunderstand signals concept
- add sorting example with a custom python function
- plpy example for triggers
- if you see `Error loading psycopg2 module: No module named 'psycopg2._psycopg'`, your local python and db's versions don't match
- including ORM will only work when django project is on the same host, which is rare. the only real way is to install the whole code on the db host
- there is certain danger of getting them out of hand
- provision custom postgres container with plpythonu and your code so ORM is accessible
- if you see this:

```
django.db.utils.ProgrammingError: language "plpython3u" does not exist
HINT:  Use CREATE LANGUAGE to load the language into the database.
```

you haven't migrated
- python versions is a mess in debian, use pyenv in docker images for plpython?

## Installation for development

Install project locally: `pip install -e .`

Django-plpy [django-environ](https://github.com/joke2k/django-environ) for passing the necessary env over dotenv,
database for creds in particular. See .env_template for possible env variables.
