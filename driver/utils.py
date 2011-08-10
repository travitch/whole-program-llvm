from subprocess import *
import collections
import errno
import os
import re
import sys

fullSelfPath = os.path.realpath(__file__)
prefix = os.path.dirname(fullSelfPath)
driverDir = prefix

# This class applies filters to GCC argument lists.  It has a few
# default arguments that it records, but does not modify the argument
# list at all.  It can be subclassed to change this behavior.
#
# The idea is that all flags accepting a parameter must be specified
# so that they know to consume an extra token from the input stream.
# Flags and arguments can be recorded in any way desired by providing
# a callback.  Each callback/flag has an arity specified - zero arity
# flags (such as -v) are provided to their callback as-is.  Higher
# arities remove the appropriate number of arguments from the list and
# pass them to the callback with the flag.
#
# Most flags can be handled with a simple lookup in a table - these
# are exact matches.  Other flags are more complex and can be
# recognized by regular expressions.  All regular expressions must be
# tried, obviously.  The first one that matches is taken, and no order
# is specified.  Try to avoid overlapping patterns.
class ArgumentListFilter(object):
    def __init__(self, inputList, exactMatches={}, patternMatches={}):
        defaultArgExactMatches = {
            '-o' : (1, ArgumentListFilter.outputFileCallback),
            '-E' : (0, ArgumentListFilter.preprocessOnlyCallback),
            '--verbose' : (0, ArgumentListFilter.verboseFlagCallback),
            '--param' : (1, ArgumentListFilter.defaultOneArgument),
            '-aux-info' : (1, ArgumentListFilter.defaultOneArgument),
            # Preprocessor assertion
            '-A' : (1, ArgumentListFilter.defaultOneArgument),
            '-D' : (1, ArgumentListFilter.defaultOneArgument),
            '-U' : (1, ArgumentListFilter.defaultOneArgument),
            # Dependency generation
            '-MT' : (1, ArgumentListFilter.defaultOneArgument),
            '-MQ' : (1, ArgumentListFilter.defaultOneArgument),
            '-MF' : (1, ArgumentListFilter.defaultOneArgument),
            '-MD' : (1, ArgumentListFilter.defaultOneArgument),
            '-MMD' : (1, ArgumentListFilter.defaultOneArgument),
            # Include
            '-I' : (1, ArgumentListFilter.defaultOneArgument),
            '-idirafter' : (1, ArgumentListFilter.defaultOneArgument),
            '-include' : (1, ArgumentListFilter.defaultOneArgument),
            '-imacros' : (1, ArgumentListFilter.defaultOneArgument),
            '-iprefix' : (1, ArgumentListFilter.defaultOneArgument),
            '-iwithprefix' : (1, ArgumentListFilter.defaultOneArgument),
            '-iwithprefixbefore' : (1, ArgumentListFilter.defaultOneArgument),
            '-isystem' : (1, ArgumentListFilter.defaultOneArgument),
            '-isysroot' : (1, ArgumentListFilter.defaultOneArgument),
            '-iquote' : (1, ArgumentListFilter.defaultOneArgument),
            '-imultilib' : (1, ArgumentListFilter.defaultOneArgument),
            # Language
            '-x' : (1, ArgumentListFilter.defaultOneArgument),
            # Component-specifiers
            '-Xpreprocessor' : (1, ArgumentListFilter.defaultOneArgument),
            '-Xassembler' : (1, ArgumentListFilter.defaultOneArgument),
            '-Xlinker' : (1, ArgumentListFilter.defaultOneArgument),
            # Linker
            '-l' : (1, ArgumentListFilter.defaultOneArgument),
            '-L' : (1, ArgumentListFilter.defaultOneArgument),
            '-T' : (1, ArgumentListFilter.defaultOneArgument),
            '-u' : (1, ArgumentListFilter.defaultOneArgument),
            }

        # The default pattern only recognizes input filenames.  Flags can also
        # be recognized here.
        defaultArgPatterns = {
            r'^.+\.(c|cc|cpp|C|cxx|i|s)$' : (0, ArgumentListFilter.inputFileCallback),
            }

        self.filteredArgs = []
        self.inputFiles = []
        self.outputFilename = None
        self.isVerbose = False
        self.isPreprocessOnly = False
        self.isAssembly = False

        argExactMatches = dict(defaultArgExactMatches)
        argExactMatches.update(exactMatches)
        argPatterns = dict(defaultArgPatterns)
        argPatterns.update(patternMatches)

        self._inputArgs = collections.deque(inputList)
        while len(self._inputArgs) > 0:
            # Get the next argument
            currentItem = self._inputArgs.popleft()
            # First, see if this exact flag has a handler in the table.
            # This is a cheap test.  Otherwise, see if the input matches
            # some pattern with a handler that we recognize
            if currentItem in argExactMatches:
                (arity, handler) = argExactMatches[currentItem]
                flagArgs = self._shiftArgs(arity)
                handler(self, currentItem, *flagArgs)
            else:
                matched = False
                for pattern, (arity, handler) in argPatterns.iteritems():
                    if re.match(pattern, currentItem):
                        flagArgs = self._shiftArgs(arity)
                        handler(self, currentItem, *flagArgs)
                        matched = True
                        break
                # If no action has been specified, this is a zero-argument
                # flag that we should just keep.
                if not matched:
                    self.keepArgument(currentItem)

    def _shiftArgs(self, nargs):
        ret = []
        while nargs > 0:
            a = self._inputArgs.popleft()
            ret.append(a)
            nargs = nargs - 1
        return ret

    def keepArgument(self, arg):
        self.filteredArgs.append(arg)

    def outputFileCallback(self, flag, filename):
        self.outputFilename = filename
        self.keepArgument(flag)
        self.keepArgument(filename)

    def preprocessOnlyCallback(self, flag):
        self.isPreprocessOnly = True
        self.keepArgument(flag)

    def verboseFlagCallback(self, flag):
        self.isVerbose = True

    def inputFileCallback(self, infile):
        self.inputFiles.append(infile)
        self.keepArgument(infile)
        if re.search('\\.s', infile):
            self.isAssembly = True

    def defaultOneArgument(self, flag, arg):
        self.keepArgument(flag)
        self.keepArgument(arg)

    def defaultNoArgument(self, flag):
        self.keepArgument(flag)

def getCompiler(isCxx):
    cstring = os.getenv('LLVM_COMPILER')
    pfx = ''
    if os.getenv('LLVM_GCC_PREFIX') is not None:
        pfx = os.getenv('LLVM_GCC_PREFIX')

    if cstring == 'clang' and isCxx:
        return ['clang++']
    elif cstring == 'clang' and not isCxx:
        return ['clang']
    elif cstring == 'dragonegg' and isCxx:
        return ['{0}g++'.format(pfx)]
    elif cstring == 'dragonegg' and not isCxx:
        return ['{0}gcc'.format(pfx)]

    print('Error: invalid LLVM_COMPILER: {0}'.format(cstring))
    sys.exit(-1)

def getBitcodeCompiler(isCxx):
    cc = getCompiler(isCxx)
    cstring = os.getenv('LLVM_COMPILER')
    if cstring == 'clang':
        return cc + ['-emit-llvm']
    elif cstring == 'dragonegg':
        pth = os.getenv('LLVM_DRAGONEGG_PLUGIN')
        # Pass -B here so that, when gcc calls as to assemble the
        # output, it invokes llvm-as instead of the system assembler
        # (which does not understand llvm assembly)
        return cc + [ '-B', driverDir, # '-specs=llvm-specs',
                     '-fplugin={0}'.format(pth), '-fplugin-arg-dragonegg-emit-ir']

    print('Error: invalid LLVM_COMPILER: {0}'.format(cstring))

def buildObject(cmd, isCxx):
    objCompiler = getCompiler(isCxx)
    objCompiler.extend(cmd)
    proc = Popen(objCompiler)
    rc = proc.wait()
    if rc != 0:
        sys.exit(rc)

# This command does not have the executable with it
def buildAndAttachBitcode(cmd, isCxx):
    af = ArgumentListFilter(cmd)
    if len(af.inputFiles) == 0 or af.isAssembly:
        return
    bcc = getBitcodeCompiler(isCxx)
    bcc.extend(cmd)
    bcc.append('-c')
    proc = Popen(bcc)
    # FIXME: if clang, attach bitcode (dragonegg does it in as)
    sys.exit(proc.wait())


