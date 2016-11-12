#!/usr/bin/env python
"""This does some simple sanity checks on the configuration.

It attempts to print informative results of that check.
Hopefully never dumping a python stack trace.

"""

import sys

from .checker import Checker

def main():
    return Checker().check()


if __name__ == '__main__':
    sys.exit(main())
