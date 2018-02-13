"""
Utility functions used across SIM system application.
Author: Weiyang Wang <wew168@ucsd.edu>
"""

from __future__ import print_function
from sys import stderr
import time

# Debug setting
DEBUG = True
# Escape string
ESCSTR = 'xyz'


# Enable print to stderr
def eprint(*args, **kwargs):
    print(*args, file=stderr, **kwargs)


# debug print
def dprint(*args, **kwargs):
    if DEBUG:
        eprint("DEBUG", *args, **kwargs)


# millisecond time
def mtime():
    return int(round(time.time() * 1000))