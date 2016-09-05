# coding: utf-8
# pylint: disable=W0621,C0103,R0903
from __future__ import unicode_literals, print_function

import os


# processing modules; in the order they are run
MODULES = [
    'cadfael.modules.inode',
    'cadfael.modules.x-mach-binary',
]

# default database location
DBADDR = '127.0.0.1:27017'

# the directory to store files we have issues parsing
FAULTS = os.path.join(os.path.abspath('..'), 'faults')

CADFAEL = None
