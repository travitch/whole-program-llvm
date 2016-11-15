#!/usr/bin/env python
"""This tool can be used two ways.

The ELF or MACH-O section contains
absolute paths to all of its constituent bitcode files.  This utility
reads the section and links together all of the named bitcode files.

If the passed in file is a binary executable it will extract the
file paths in the bitcode section from the provided ELF or MACH-O object
and assemble them into an actual bitcode file.

If the passed in file is a static library it will extract the
constituent ELF or MACH-O objects and read their bitcode sections and
create a LLVM Bitcode archive from the bitcode files. That said, there
is a command line option (--bitcode -b) that allows one to extract the
bitcode into a module rather than an archive.

The above language is deliberately vague, since ELF contains a
.llvm_bc section, whereas the MACH-O contains a segment called __LLVM
that contains a section called __llvm_bc.

"""
from __future__ import absolute_import

import sys

from .extraction import extraction

def main():
    """ The entry point to extract-bc.
    """
    try:
        extraction()
    except Exception:
        pass
    return 0

if __name__ == '__main__':
    sys.exit(main())
