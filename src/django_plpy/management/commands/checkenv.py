from platform import python_version

from django.core.management.base import BaseCommand
from django.db import transaction

from django_plpy.utils import sem_to_minor
from django_plpy.installer import get_python_info


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

        if sem_to_minor(info["version"]) != sem_to_minor(python_version()):
            self.stderr.write(
                f"Postgres python and this python's versions don't match, local version: {python_version()}."
                f"Django-plpy Django ORM cannot be used in triggers."
            )
        elif info["version"] != python_version():
            self.stdout.write(
                f"Minor versions match, local version: {python_version()}. "
                f"Django-plpy Django ORM can be used in triggers."
            )
        else:
            self.stdout.write(f"Full version match: {python_version()}")
