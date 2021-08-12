#!/usr/bin/env python
"""Since we are trying to distribute Django applications as Python Packages,
it is important that some commands (such `migrate`) are available from within
the installation of the package without the need of copying the source code.

Because of that ``pyscaffoldext-django`` moves the generated ``manage.py`` file
to become the package's ``__main__.py`` file. This way all the commands that
could be run before as ``python3 manage.py <COMMAND>`` can now be run as
``python3 -m django_plpy <COMMAND>``, in a straight forward fashion just after
a ``pip3 install``.

This file is a executable stub that simply calls ``__main__.py:main()`` for
the sake of backward compatibility of the developer's workflow.
"""
import os
import sys

# This makes the package usable even without being installed with pip
# (redundant in the case the developer uses `python setup.py develop`)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


if __name__ == "__main__":
    from django_plpy.__main__ import main

    main()
