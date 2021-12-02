from django.contrib.admin import ModelAdmin
from django.contrib import admin

from tests.books.models import Book


@admin.register(Book)
class BookAdmin(ModelAdmin):
    list_display = ("name", "amount_sold", "amount_stock", "stock_days_left")
