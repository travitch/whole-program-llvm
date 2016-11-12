#!/usr/bin/env python
"""This is a wrapper around the real compiler.

It first invokes a real compiler to generate
an object file.  Then it invokes a bitcode
compiler to generate a parallel bitcode file.
It records the location of the bitcode in an
ELF section of the object file so that it can be
found later after all of the objects are
linked into a library or executable.
"""

import sys, os

from .compilers import getBuilder, buildObject, buildAndAttachBitcode, logging

from .logconfig import *

_logger = logging.getLogger(__name__)

def main():
    try:
        rc = 1
        cmd = list(sys.argv)
        cmd = cmd[1:]
        builder = getBuilder(cmd, False)
        rc = buildObject(builder)
        if rc == 0 and not os.environ.get('WLLVM_CONFIGURE_ONLY', False):
            buildAndAttachBitcode(builder)
    except Exception as e:
        _logger.debug('wllvm: exception case: {0}\n'.format(e))
        pass
    return rc


if __name__ == '__main__':
    sys.exit(main())
