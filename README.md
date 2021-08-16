# django-plpy

Django utilities for Postgres PL/Python. Work in progress 

## Description


### Installation
- python 3.6.9
- postgres 10 and postgresql-plpython3

- add django-plpy to INSTALLED_APPS
- migrate
## Usage
+ install simple python function
+ install command
+ trigger (https://django-pgtrigger.readthedocs.io/en/latest/tutorial.html#keeping-a-field-in-sync-with-another)
+ install function with TD
+ load virtualenv
+ load project
+ access ORM within function
+ some functions for django lookups
+ manage py commands

## Under the hood

- about python versions in postgres
- how the code is installed
- often django beginners misunderstand signals concept
- add sorting example with a custom python function
- plpy example for triggers

- including ORM will only work when django project is on the same host, which is rare. the only real way is to install the whole code on the db host
- there is certain danger of getting them out of hand

## Installation for development

Install project locally: `pip install -e .`

Django-plpy [django-environ](https://github.com/joke2k/django-environ) for passing the necessary env over dotenv,
database for creds in particular. See .env_template for possible env variables.
