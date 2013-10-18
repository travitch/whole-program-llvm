from subprocess import *
import collections
import pprint
import logging
import errno
import os
import re
import sys
import tempfile

fullSelfPath = os.path.realpath(__file__)
prefix = os.path.dirname(fullSelfPath)
driverDir = prefix

# This is a bit hacky.
# We cannot do
# from .popenwrapper import Popen
# OR
# from driver.popenwrapper import Popen
# because then 'as' will not succesfully import us (wllvm/wllvm++ can
# successfully import however).
#
# Using
# from popenwrapper import Popen
# will allow 'as' to import us but then wllvm/wllvm++ will not be able to.
#
# The work around is to put this directory in the search path for modules.
sys.path.insert(0,driverDir)
from popenwrapper import Popen

# Environmental variable for path to compiler tools (clang/llvm-link etc..)
llvmCompilerPathEnv = 'LLVM_COMPILER_PATH'

# This is the ELF section name inserted into binaries
elfSectionName='.llvm_bc'

# Internal logger
_logger = logging.getLogger(__name__)

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
            '-c' : (0, ArgumentListFilter.compileOnlyCallback),
            '-E' : (0, ArgumentListFilter.preprocessOnlyCallback),
            '-S' : (0, ArgumentListFilter.assembleOnlyCallback),
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
        self.isAssembleOnly = False
        self.isAssembly = False
        self.isCompileOnly = False

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
                for pattern, (arity, handler) in argPatterns.items():
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

    def assembleOnlyCallback(self, flag):
        self.isAssembleOnly = True
        self.keepArgument(flag)

    def verboseFlagCallback(self, flag):
        self.isVerbose = True

    def compileOnlyCallback(self, flag):
        self.isCompileOnly = True
        self.keepArgument(flag)

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

    def getOutputFilename(self):
        if self.outputFilename is not None:
            return self.outputFilename
        elif self.isCompileOnly:
            (root, ext) = os.path.splitext(self.inputFiles[0])
            return '{0}.o'.format(root)
        else:
            return 'a.out'

# Same as above, but change the name of the output filename when
# building the bitcode file so that we don't clobber the object file.
class ClangBitcodeArgumentListFilter(ArgumentListFilter):
    def __init__(self, arglist):
        localCallbacks = { '-o' : (1, ClangBitcodeArgumentListFilter.outputFileCallback) }
        super(ClangBitcodeArgumentListFilter, self).__init__(arglist, exactMatches=localCallbacks)

    def outputFileCallback(self, flag, filename):
        self.outputFilename = filename


# Static class that allows the type of a file to be checked.
class FileType(object):
  # Provides int -> str map
  revMap = { }

  @classmethod
  def getFileType(cls, fileName):
      # This is a hacky way of determining
      # the type of file we are looking at.
      # Maybe we should use python-magic instead?

      fileP = Popen(['file',fileName], stdout=PIPE)
      output = fileP.communicate()[0]
      output = output.decode()
      if 'ELF' in output and 'executable' in output:
          return cls.EXECUTABLE
      elif 'current ar archive' in output:
          return cls.ARCHIVE
      elif 'ELF' in output and 'relocatable' in output:
          return cls.OBJECT
      else:
          return cls.UNKNOWN

  @classmethod
  def init(cls):
      for (index, name) in enumerate(('UNKNOWN', 'EXECUTABLE', 'OBJECT', 'ARCHIVE')):
          setattr(cls, name, index)
          cls.revMap[index] = name

# Initialise FileType static class
FileType.init()

def attachBitcodePathToObject(bcPath, outFileName):
    # Don't try to attach a bitcode path to a binary.  Unfortunately
    # that won't work.
    (root, ext) = os.path.splitext(outFileName)
    if ext not in ('.o', '.lo', '.os'):
        _logger.warning('Cannot attach bitcode path to "{0}"'.format(outFileName))
        return

    # Now just build a temporary text file with the full path to the
    # bitcode file that we'll write into the object file.
    f = tempfile.NamedTemporaryFile(mode='w+b', delete=False)
    absBcPath = os.path.abspath(bcPath)
    f.write(absBcPath.encode())
    f.write('\n'.encode())
    _logger.debug(pprint.pformat('Wrote "{0}" to file "{1}"'.format(absBcPath, f.name)))

    # Ensure buffers are flushed so that objcopy doesn't read an empty
    # file
    f.flush()
    os.fsync(f.fileno())
    f.close()

    # Now write our .llvm_bc section
    objcopyCmd = ['objcopy', '--add-section', '{0}={1}'.format(elfSectionName, f.name), outFileName]
    orc = 0

    try:
        if os.path.getsize(outFileName) > 0:
            objProc = Popen(objcopyCmd)
            orc = objProc.wait()
    except OSError:
        # configure loves to immediately delete things, causing issues for
        # us here.  Just ignore it
        os.remove(f.name)
        sys.exit(0)

    os.remove(f.name)

    if orc != 0:
        _logger.error('objcopy failed with {0}'.format(orc))
        sys.exit(-1)

class BuilderBase(object):
    def __init__(self, cmd, isCxx, prefixPath=None):
        self.cmd = cmd
        self.isCxx = isCxx

        # Used as prefix path for compiler
        if prefixPath:
          self.prefixPath = prefixPath

          # Ensure prefixPath has trailing slash
          if self.prefixPath[-1] != os.path.sep:
            self.prefixPath = self.prefixPath + os.path.sep

          # Check prefix path exists
          if not os.path.exists(self.prefixPath):
            errorMsg='Path to compiler "{0}" does not exist'.format(self.prefixPath)
            _logger.error(errorMsg)
            raise Exception(errorMsg)

        else:
          self.prefixPath = ''

class ClangBuilder(BuilderBase):
    def __init__(self, cmd, isCxx, prefixPath=None):
        super(ClangBuilder, self).__init__(cmd, isCxx, prefixPath)

    def getBitcodeCompiler(self):
        cc = self.getCompiler()
        return cc + ['-emit-llvm']

    def getCompiler(self):
        if self.isCxx:
            return ['{0}clang++'.format(self.prefixPath)]
        else:
            return ['{0}clang'.format(self.prefixPath)]

    def getBitcodeArglistFilter(self):
        return ClangBitcodeArgumentListFilter(self.cmd)

    def getBitcodeFileName(self, argFilter):
        (dirs, baseFile) = os.path.split(argFilter.getOutputFilename())
        bcfilename = os.path.join(dirs, '.{0}.bc'.format(baseFile))

        return bcfilename

    def extraBitcodeArgs(self, argFilter):
        bcPath = self.getBitcodeFileName(argFilter)

        return ['-o', bcPath]

    def attachBitcode(self, argFilter):
        bcname = self.getBitcodeFileName(argFilter)
        outFile = argFilter.getOutputFilename()
        attachBitcodePathToObject(bcname, outFile)

class DragoneggBuilder(BuilderBase):
    def __init__(self, cmd, isCxx, prefixPath=None):
        super(DragoneggBuilder, self).__init__(cmd, isCxx, prefixPath)

    def getBitcodeCompiler(self):
        pth = os.getenv('LLVM_DRAGONEGG_PLUGIN')
        cc = self.getCompiler()
        # We use '-B' to tell gcc where to look for an assembler.
        # When we build LLVM bitcode we do not want to use the GNU assembler,
        # instead we want gcc to use our own assembler (see driver/as).
        return cc + ['-B', driverDir, '-fplugin={0}'.format(pth),
                     '-fplugin-arg-dragonegg-emit-ir']

    def getCompiler(self):
        pfx = ''
        if os.getenv('LLVM_GCC_PREFIX') is not None:
            pfx = os.getenv('LLVM_GCC_PREFIX')

        if self.isCxx:
            return ['{0}{1}g++'.format(self.prefixPath, pfx)]
        else:
            return ['{0}{1}gcc'.format(self.prefixPath, pfx)]

    def getBitcodeArglistFilter(self):
        return ArgumentListFilter(self.cmd)

    # Don't need to do anything since the -B flag in the bitcode
    # compiler and the assembly stub handles it
    def attachBitcode(self, argFilter):
        pass

    def extraBitcodeArgs(self, argFilter):
        return []


def getBuilder(cmd, isCxx):
    compilerEnv = 'LLVM_COMPILER'
    cstring = os.getenv(compilerEnv)
    pathPrefix = os.getenv(llvmCompilerPathEnv) # Optional
    _logger.info('WLLVM compiler using {0}'.format(cstring))
    if pathPrefix:
      _logger.info('WLLVM compiler path prefix "{0}"'.format(pathPrefix))

    if cstring == 'clang':
        return ClangBuilder(cmd, isCxx, pathPrefix)
    elif cstring == 'dragonegg':
        return DragoneggBuilder(cmd, isCxx, pathPrefix)
    elif cstring == None:
        errorMsg = ' No compiler set. Please set environment variable ' + compilerEnv
        _logger.critical(errorMsg)
        raise Exception(errorMsg)
    else:
        errorMsg= compilerEnv + '=' + str(cstring) + ' : Invalid compiler type'
        _logger.critical(errorMsg)
        raise Exception(errorMsg)

def buildObject(builder):
    objCompiler = builder.getCompiler()
    objCompiler.extend(builder.cmd)
    proc = Popen(objCompiler)
    rc = proc.wait()
    if rc != 0:
        sys.exit(rc)

def isLinkOption(arg):
    return arg == '-pthread' or arg.startswith('-l') or arg.startswith('-Wl,')

# This command does not have the executable with it
def buildAndAttachBitcode(builder):
    af = builder.getBitcodeArglistFilter()
    if len(af.inputFiles) == 0 or af.isAssembly or af.isAssembleOnly:
        return
    bcc = builder.getBitcodeCompiler()
    bcc.extend(af.filteredArgs)
    bcc.append('-c')
    bcc.extend(builder.extraBitcodeArgs(af))
    # Filter out linker options since we are compiling with -c.  If we
    # leave them in, clang will emit warnings.  Some configure scripts
    # check to see if there was any output on stderr instead of the
    # return code of commands, so warnings about unused link flags can
    # cause spurious failures here.
    bcc = [arg for arg in bcc if not isLinkOption(arg)]
    proc = Popen(bcc)
    rc = proc.wait()
    if rc == 0:
        builder.attachBitcode(af)
    sys.exit(rc)

