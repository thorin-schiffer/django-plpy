from platform import python_version

from django.core.management.base import BaseCommand
from django.db import transaction

from django_plpy.builder import get_python_info


class Command(BaseCommand):
    """
    Command class for checking if the python versions within the database and the local interpreter
    """

    help = "Checks python information within the plpython"

    @transaction.atomic
    def handle(self, *args, **options):
        """
        Handles the task execution
        @param args: args of the command
        @param options: options of the command
        """
        info = get_python_info()
        self.stdout.write(f"Database's Python version: {info['version']}")

        if info["version"] != python_version():
            self.stderr.write(
                f"Postgres python and this python's versions don't match, local version: {python_version()}"
            )
