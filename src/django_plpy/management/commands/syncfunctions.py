from django.core.management.base import BaseCommand
from django.db import transaction

from django_plpy.builder import pl_functions, install_function, pl_triggers


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

        self.stdout.write("Syncing functions")
        for function_name, f in pl_functions.items():
            self.stdout.write(f"Syncing {function_name}")
            install_function(f)
            self.stdout.write(f"Installed {function_name}")

        self.stdout.write("Syncing triggers")
        for function_name, f in pl_triggers.items():
            self.stdout.write(f"Syncing {function_name}")
            install_function(f[0], f[1])
            self.stdout.write(f"Installed {function_name}")
