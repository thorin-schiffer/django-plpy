from platform import python_version

from django.core.management.base import BaseCommand
from django.db import transaction

from django_plpy.pl_python.builder import get_python_info


class Command(BaseCommand):
    help = 'Checks python information within the plpython'

    @transaction.atomic
    def handle(self, *args, **options):
        info = get_python_info()
        self.stdout.write(f"Python version: {info['version']}")

        if info['version'] != python_version():
            self.stderr.write(
                f"Postgres python and this python's versions don't match: {python_version()}"
            )
