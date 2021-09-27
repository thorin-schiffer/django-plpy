from django.db.models import Model, CharField, IntegerField, Func, F

from django_plpy.installer import plfunction, pltrigger


@plfunction
def pl_max(a: int, b: int) -> int:
    if a > b:
        return a
    return b


@pltrigger(event="INSERT", when="BEFORE", table="books_book")
def pl_trigger(td, plpy):
    td["new"]["name"] = td["new"]["name"] + "test"


@plfunction
def pl_test_django():
    import django

    print(django)


class Book(Model):
    name = CharField(max_length=10)
    amount_stock = IntegerField(default=20)
    amount_sold = IntegerField(default=10)

    def get_max(self):
        return (
            Book.objects.annotate(
                max_value=Func(F("amount_sold"), F("amount_stock"), function="pl_max")
            )
            .get(pk=self.pk)
            .max_value
        )
