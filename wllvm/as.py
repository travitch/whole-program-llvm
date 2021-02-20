#!/usr/bin/env python
"""This is the (dragonegg) assembler phase.

This variant is only invoked during the second compilation where we
are building bitcode.  The compiler has already been instructed to
generate LLVM IR; the compiler then tries to assemble it into an
object file.  The standard assembler doesn't understand LLVM bitcode,
so we interpose and use the llvm-as command to build a bitcode file.
We leave the bitcode in place, but record its full absolute path in
the corresponding object file (which was created in the first
compilation phase by the real compiler).  We'll link this together at
a later stage.

In the pip version the main below is a console script called wllvm-as.
Since we cannot tell gcc what our assember is called, only which
directory it should look for the assembler "as" in, we have to make a
"hidden" directory that we can use to pass gcc. It needs to be hidden
since we have no control over the user's PATH and certainly do not
want our assembler to accidently override the user's assembler.

This should explain:

./dragonegg_as/as

in the pip egg, and in the repository.

"""

from __future__ import absolute_import

import sys

import os

#from subprocess import *

from .compilers import llvmCompilerPathEnv

from .popenwrapper import Popen

from .arglistfilter import ArgumentListFilter

from .logconfig import logConfig

# Internal logger
_logger = logConfig(__name__)


class BCFilter(ArgumentListFilter):
    """ Argument filter for the assembler.
    """
    def __init__(self, arglist):
        self.bcName = None
        self.outFileName = None
        localCallbacks = {'-o' : (1, BCFilter.outFileCallback)}
        super().__init__(arglist, exactMatches=localCallbacks)

    def outFileCallback(self, flag, name):
        """ Callback for the -o flag.
        """
        _logger.debug('BCFilter.outFileCallback %s %s', flag, name)
        self.outFileName = name

def main():
    """ Entry point to the assembler 'as' in the dragonegg realm.
    """
    argFilter = BCFilter(sys.argv[1:])
    # Since this is just the assembler, there should only ever be one file
    try:
        [infile] = argFilter.inputFiles
    except ValueError:
        _logger.debug('Input file argument not detected, assuming stdin.')
        infile = "-"

    # set llvm-as
    llvmAssembler = 'llvm-as'
    if os.getenv(llvmCompilerPathEnv):
        llvmAssembler = os.path.join(os.getenv(llvmCompilerPathEnv), llvmAssembler)

    # Now compile this llvm assembly file into a bitcode file.  The output
    # filename is the same as the object with a .bc appended
    if not argFilter.outFileName:
        _logger.error('Output file argument not found.')
        sys.exit(1)

    fakeAssembler = [llvmAssembler, infile, '-o', argFilter.outFileName]

    asmProc = Popen(fakeAssembler)
    realRet = asmProc.wait()

    if realRet != 0:
        _logger.error('llvm-as failed')
        sys.exit(realRet)

    sys.exit(realRet)


if __name__ == '__main__':
    sys.exit(main())
