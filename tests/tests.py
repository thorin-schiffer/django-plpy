import os
from platform import python_version
from typing import List

from django.core.management import call_command
from django.db import connection
from django.db.models import Func, F, Transform
from django.db.models import IntegerField
from django_plpy.builder import (
    build_pl_function,
    build_pl_trigger_function,
)
from django_plpy.installer import (
    install_function,
    plfunction,
    pltrigger,
    get_python_info,
    pl_triggers,
    pl_functions,
)
from django_plpy.utils import sem_to_minor
from pytest import fixture, mark, skip, raises

from tests.books.models import Book


@fixture
def book(db):
    return Book.objects.create(name="book")


@fixture
def pl_simple_function():
    return """
CREATE FUNCTION pl_max (a integer, b integer)
  RETURNS integer
AS $$
  if a > b:
    return a
  return b
$$ LANGUAGE plpython3u;
"""


@fixture(autouse=True)
def clean_triggers_and_functions(db):
    with connection.cursor() as cursor:
        cursor.execute(
            "DROP TRIGGER IF EXISTS pl_trigger_trigger ON books_book CASCADE;"
        )
        cursor.execute("DROP FUNCTION IF EXISTS pl_max;")


def test_simple_function(pl_simple_function, db):
    with connection.cursor() as cursor:
        cursor.execute(pl_simple_function)
        cursor.execute("select pl_max(10, 20)")
        row = cursor.fetchone()
    assert row[0] == 20


def pl_max(a: int, b: int) -> int:
    if a > b:
        return a
    return b


def test_generate_simple_pl_python_from_function(db):
    pl_python_function = build_pl_function(pl_max)
    with connection.cursor() as cursor:
        cursor.execute(pl_python_function)
        cursor.execute("select pl_max(10, 20)")
        row = cursor.fetchone()
    assert row[0] == 20


@fixture
def simple_function(db):
    install_function(pl_max)


def test_call_simple_function_from_django_orm(simple_function, book):
    result = Book.objects.annotate(
        max_value=Func(F("amount_sold"), F("amount_stock"), function="pl_max")
    )
    assert result[0].max_value == result[0].amount_stock


def test_custom_lookup_with_function(simple_function, book):
    def plsquare(a: int) -> int:
        return a * a

    install_function(plsquare)

    class PySquare(Transform):
        lookup_name = "plsquare"
        function = "plsquare"

    IntegerField.register_lookup(PySquare)
    assert Book.objects.filter(amount_stock__plsquare=400).exists()
    # of course also mixes with other lookups
    assert Book.objects.filter(amount_stock__plsquare__gt=10).exists()


def test_plfunction_decorator_registers():
    @plfunction
    def pl_max(a: int, b: int) -> int:
        if a > b:
            return a
        return b

    assert pl_max, {} in pl_functions.values()


def test_generate_trigger_function(db):
    def pl_trigger(td, plpy):
        # mind triggers don't return anything
        td["new"]["name"] = td["new"]["name"] + "test"
        td["new"]["amount_sold"] = plpy.execute("SELECT count(*) FROM books_book")[0][
            "count"
        ]

    pl_python_trigger_function = build_pl_trigger_function(
        pl_trigger, event="INSERT", when="BEFORE", table="books_book"
    )
    with connection.cursor() as cursor:
        cursor.execute(pl_python_trigger_function)
    book = Book.objects.create(name="book", amount_sold=1)
    book.refresh_from_db()
    assert book.name == "booktest"
    assert book.amount_sold == 0

    with connection.cursor() as cursor:
        cursor.execute(
            "DROP TRIGGER IF EXISTS pl_trigger_trigger ON books_book CASCADE;"
        )


def test_pltrigger_decorator_registers():
    @pltrigger(event="INSERT", when="BEFORE", table="books_book")
    def pl_trigger_test_decorator_registers(td, plpy):
        pass

    f, params = next(
        x
        for x in list(pl_triggers.values())
        if x[0].__name__ == "pl_trigger_test_decorator_registers"
    )
    assert params["event"] == "INSERT"
    assert params["when"] == "BEFORE"
    assert params["table"] == "books_book"


@fixture
def same_python_versions(db):
    info = get_python_info()
    if sem_to_minor(info["version"]) != sem_to_minor(python_version()):
        skip("This test can only succeed if db and host python versions match")


@mark.django_db(transaction=True)
def test_trigger_model(same_python_versions):
    @pltrigger(event="INSERT", when="BEFORE", model=Book, extra_env=dict(os.environ))
    def pl_trigger_trigger_model(new: Book, old: Book, td, plpy):
        # don't use save method here, it will kill the database because of recursion
        new.amount_stock = 123

    call_command("syncfunctions")

    book = Book.objects.create(name="book")
    book.refresh_from_db()
    assert book.amount_stock == 123


def test_function_different_arguments(db):
    def pl_test_arguments(
        list_str: List[str], list_int: List[int], flag: bool, number: float
    ) -> int:
        return 1

    install_function(pl_test_arguments)
    with connection.cursor() as cursor:
        cursor.callproc("pl_test_arguments", [["a", "b"], [1, 2], True, 1.5])


def test_function_unknown_type(db):
    def pl_test_arguments(arg: Book) -> int:
        return 1

    with raises(RuntimeError):
        install_function(pl_test_arguments)


def test_function_not_annotated(db):
    def pl_test_arguments(arg):
        return 1

    with raises(RuntimeError):
        install_function(pl_test_arguments)


@mark.django_db(transaction=True)
def test_sync_functions():
    @plfunction
    def pl_max(a: int, b: int) -> int:
        if a > b:
            return a
        return b

    call_command("syncfunctions")
    with connection.cursor() as cursor:
        cursor.execute("select pl_max(10, 20)")
        row = cursor.fetchone()
    assert row[0] == 20


@mark.django_db(transaction=True)
def test_check_env():
    call_command("checkenv")
