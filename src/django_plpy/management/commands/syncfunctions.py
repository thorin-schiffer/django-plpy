from django.core.management.base import BaseCommand
from django.db import transaction

from django_plpy.installer import (
    pl_functions,
    pl_triggers,
)
from django_plpy.installer import sync_functions


class Command(BaseCommand):
    """
    Command class for installing or overwriting the plpy functions to the database
    """

    help = "Syncs PL/Python functions, decorated with @plfunction and @pltrigger"

    @transaction.atomic
    def handle(self, *args, **options):
        """
        Handles the task execution
        @param args: args of the command
        @param options: options of the command
        """
        if not pl_functions and not pl_triggers:
            self.stdout.write("No PL/Python functions found")

        sync_functions()
        self.stdout.write(
            f"Synced {len(pl_functions)} functions and {len(pl_triggers)} triggers"
        )
