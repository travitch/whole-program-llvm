from __future__ import absolute_import
from __future__ import print_function

from subprocess import *
import collections
import pprint
import logging
import errno
import os
import re
import sys
import tempfile


from .popenwrapper import Popen

fullSelfPath = os.path.realpath(__file__)
prefix = os.path.dirname(fullSelfPath)
driverDir = prefix
asDir = os.path.abspath(os.path.join(driverDir, 'dragonegg_as'))


# Environmental variable for path to compiler tools (clang/llvm-link etc..)
llvmCompilerPathEnv = 'LLVM_COMPILER_PATH'

# This is the ELF section name inserted into binaries
elfSectionName='.llvm_bc'

# These are the MACH_O segment and section name
# The SegmentName was __LLVM. Changed to __WLLVM to avoid clashing
# with a segment that ld now uses (since MacOS X 10.11.3?)
darwinSegmentName='__WLLVM'
darwinSectionName='__llvm_bc'


# Internal logger
_logger = logging.getLogger(__name__)

# Flag for dumping
DUMPING = False


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
            '--param' : (1, ArgumentListFilter.defaultBinaryCallback),
            '-aux-info' : (1, ArgumentListFilter.defaultBinaryCallback),

            #iam: presumably the len(inputFiles) == 0 in this case
            '--version' : (0, ArgumentListFilter.compileOnlyCallback),
            '-v' : (0, ArgumentListFilter.compileOnlyCallback),

            #warnings (apart from the regex below)
            '-w' : (0, ArgumentListFilter.compileOnlyCallback),
            '-W' : (0, ArgumentListFilter.compileOnlyCallback),


            #iam: if this happens, then we need to stop and think.
            '-emit-llvm' : (0, ArgumentListFilter.abortUnaryCallback),

            #iam: buildworld and buildkernel use these flags
            '-pipe' : (0, ArgumentListFilter.compileUnaryCallback),
            '-undef' : (0, ArgumentListFilter.compileUnaryCallback),
            '-nostdinc' : (0, ArgumentListFilter.compileUnaryCallback),
            '-nostdinc++' : (0, ArgumentListFilter.compileUnaryCallback),
            '-Qunused-arguments' : (0, ArgumentListFilter.compileUnaryCallback),
            '-no-integrated-as' : (0, ArgumentListFilter.compileUnaryCallback),
            '-integrated-as' : (0, ArgumentListFilter.compileUnaryCallback),
            #iam: gcc uses this in both compile and link, but clang only in compile
            '-pthread' : (0, ArgumentListFilter.compileUnaryCallback),
            # I think this is a compiler search path flag.  It is
            # clang only, so I don't think it counts as a separate CPP
            # flag.  Android uses this flag with its clang builds.
            '-nostdlibinc': (0, ArgumentListFilter.compileUnaryCallback),

            #iam: arm stuff
            '-mno-omit-leaf-frame-pointer' : (0, ArgumentListFilter.compileUnaryCallback),
            '-maes' : (0, ArgumentListFilter.compileUnaryCallback),
            '-mno-aes' : (0, ArgumentListFilter.compileUnaryCallback),
            '-mavx' : (0, ArgumentListFilter.compileUnaryCallback),
            '-mno-avx' : (0, ArgumentListFilter.compileUnaryCallback),
            '-mcmodel=kernel' : (0, ArgumentListFilter.compileUnaryCallback),
            '-mno-red-zone' : (0, ArgumentListFilter.compileUnaryCallback),
            '-mmmx' : (0, ArgumentListFilter.compileUnaryCallback),
            '-mno-mmx' : (0, ArgumentListFilter.compileUnaryCallback),
            '-msse' : (0, ArgumentListFilter.compileUnaryCallback),
            '-mno-sse2' : (0, ArgumentListFilter.compileUnaryCallback),
            '-msse2' : (0, ArgumentListFilter.compileUnaryCallback),
            '-mno-sse3' : (0, ArgumentListFilter.compileUnaryCallback),
            '-msse3' : (0, ArgumentListFilter.compileUnaryCallback),
            '-mno-sse' : (0, ArgumentListFilter.compileUnaryCallback),
            '-msoft-float' : (0, ArgumentListFilter.compileUnaryCallback),
            '-m3dnow' : (0, ArgumentListFilter.compileUnaryCallback),
            '-mno-3dnow' : (0, ArgumentListFilter.compileUnaryCallback),
            '-m32': (0, ArgumentListFilter.compileUnaryCallback),
            '-m64': (0, ArgumentListFilter.compileUnaryCallback),
            '-mstackrealign': (0, ArgumentListFilter.compileUnaryCallback),

            # Preprocessor assertion
            '-A' : (1, ArgumentListFilter.compileBinaryCallback),
            '-D' : (1, ArgumentListFilter.compileBinaryCallback),
            '-U' : (1, ArgumentListFilter.compileBinaryCallback),

            # Dependency generation
            '-M'  : (0, ArgumentListFilter.dependencyOnlyCallback),
            '-MM' : (0, ArgumentListFilter.dependencyOnlyCallback),
            '-MF' : (1, ArgumentListFilter.dependencyBinaryCallback),
            '-MG' : (0, ArgumentListFilter.dependencyOnlyCallback),
            '-MP' : (0, ArgumentListFilter.dependencyOnlyCallback),
            '-MT' : (1, ArgumentListFilter.dependencyBinaryCallback),
            '-MQ' : (1, ArgumentListFilter.dependencyBinaryCallback),
            '-MD' : (0, ArgumentListFilter.dependencyOnlyCallback),
            '-MMD' : (0, ArgumentListFilter.dependencyOnlyCallback),

            # Include
            '-I' : (1, ArgumentListFilter.compileBinaryCallback),
            '-idirafter' : (1, ArgumentListFilter.compileBinaryCallback),
            '-include' : (1, ArgumentListFilter.compileBinaryCallback),
            '-imacros' : (1, ArgumentListFilter.compileBinaryCallback),
            '-iprefix' : (1, ArgumentListFilter.compileBinaryCallback),
            '-iwithprefix' : (1, ArgumentListFilter.compileBinaryCallback),
            '-iwithprefixbefore' : (1, ArgumentListFilter.compileBinaryCallback),
            '-isystem' : (1, ArgumentListFilter.compileBinaryCallback),
            '-isysroot' : (1, ArgumentListFilter.compileBinaryCallback),
            '-iquote' : (1, ArgumentListFilter.compileBinaryCallback),
            '-imultilib' : (1, ArgumentListFilter.compileBinaryCallback),

            # Language
            '-ansi' : (0, ArgumentListFilter.compileUnaryCallback),
            '-pedantic' : (0, ArgumentListFilter.compileUnaryCallback),
            '-x' : (1, ArgumentListFilter.compileBinaryCallback),

            # Debug
            '-g' : (0, ArgumentListFilter.compileUnaryCallback),
            '-g0' : (0, ArgumentListFilter.compileUnaryCallback),     #iam: clang not gcc
            '-ggdb' : (0, ArgumentListFilter.compileUnaryCallback), 
            '-ggdb3' : (0, ArgumentListFilter.compileUnaryCallback), 
            '-gdwarf-2' : (0, ArgumentListFilter.compileUnaryCallback),
            '-gdwarf-3' : (0, ArgumentListFilter.compileUnaryCallback),
            '-p' : (0, ArgumentListFilter.compileUnaryCallback),
            '-pg' : (0, ArgumentListFilter.compileUnaryCallback),

            # Optimization
            '-O' : (0, ArgumentListFilter.compileUnaryCallback),
            '-O0' : (0, ArgumentListFilter.compileUnaryCallback),
            '-O1' : (0, ArgumentListFilter.compileUnaryCallback),
            '-O2' : (0, ArgumentListFilter.compileUnaryCallback),
            '-O3' : (0, ArgumentListFilter.compileUnaryCallback),
            '-Os' : (0, ArgumentListFilter.compileUnaryCallback),
            '-Ofast' : (0, ArgumentListFilter.compileUnaryCallback),
            '-Og' : (0, ArgumentListFilter.compileUnaryCallback),
            # Component-specifiers
            '-Xclang' : (1, ArgumentListFilter.compileBinaryCallback),
            '-Xpreprocessor' : (1, ArgumentListFilter.defaultBinaryCallback),
            '-Xassembler' : (1, ArgumentListFilter.defaultBinaryCallback),
            '-Xlinker' : (1, ArgumentListFilter.defaultBinaryCallback),
            # Linker
            '-l' : (1, ArgumentListFilter.linkBinaryCallback),
            '-L' : (1, ArgumentListFilter.linkBinaryCallback),
            '-T' : (1, ArgumentListFilter.linkBinaryCallback),
            '-u' : (1, ArgumentListFilter.linkBinaryCallback),
            #iam: specify the entry point
            '-e' : (1, ArgumentListFilter.linkBinaryCallback),
            # runtime library search path
            '-rpath' : (1, ArgumentListFilter.linkBinaryCallback),
            # iam: showed up in buildkernel
            '-shared' : (0, ArgumentListFilter.linkUnaryCallback),
            '-static' : (0, ArgumentListFilter.linkUnaryCallback),
            '-pie' : (0, ArgumentListFilter.linkUnaryCallback),
            '-nostdlib' : (0, ArgumentListFilter.linkUnaryCallback),
            '-nodefaultlibs' : (0, ArgumentListFilter.linkUnaryCallback),
            '-rdynamic' : (0, ArgumentListFilter.linkUnaryCallback),
            # darwin flags
            '-dynamiclib' : (0, ArgumentListFilter.linkUnaryCallback),
            '-current_version' : (1, ArgumentListFilter.linkBinaryCallback),
            '-compatibility_version' : (1, ArgumentListFilter.linkBinaryCallback),

            # dragonegg mystery argument
            '--64' : (0, ArgumentListFilter.compileUnaryCallback),

            # binutils nonsense
            '-print-multi-directory' : (0, ArgumentListFilter.compileUnaryCallback),
            '-print-multi-lib' : (0, ArgumentListFilter.compileUnaryCallback),
            '-print-libgcc-file-name' : (0, ArgumentListFilter.compileUnaryCallback),


            #
            # BD: need to warn the darwin user that these flags will rain on their parade
            # (the Darwin ld is a bit single minded)
            #
            # 1) compilation with -fvisibility=hidden causes trouble when we try to
            #    attach bitcode filenames to an object file. The global symbols in object 
            #    files get turned into local symbols when we invoke 'ld -r'
            #
            # 2) all stripping commands (e.g., -dead_strip) remove the __LLVM segment after
            #    linking
            #
            # Update: found a fix for problem 1: add flag -keep_private_externs when
            # calling ld -r.
            #
            '-Wl,-dead_strip' :  (0, ArgumentListFilter.darwinWarningLinkUnaryCallback),
            
           }

        #
        # Patterns for other command-line arguments:
        # - inputFiles
        # - objectFiles (suffix .o)
        # - libraries + linker options as in -lxxx -Lpath or -Wl,xxxx
        # - preprocessor options as in -DXXX -Ipath
        # - compiler warning options: -W....
        # - optimiziation and other flags: -f...
        #
        defaultArgPatterns = {
            r'^.+\.(c|cc|cpp|C|cxx|i|s|S)$' : (0, ArgumentListFilter.inputFileCallback),
            #iam: the object file recogition is not really very robust, object files
            # should be determined by their existance and contents...
            r'^.+\.(o|lo|So|so|po|a|dylib)$' : (0, ArgumentListFilter.objectFileCallback),
            #iam: library.so.4.5.6 probably need a similar pattern for .dylib too.
            r'^.+\.dylib(\.\d)+$' : (0, ArgumentListFilter.objectFileCallback),
            r'^.+\.(So|so)(\.\d)+$' : (0, ArgumentListFilter.objectFileCallback),
            r'^-(l|L).+$' : (0, ArgumentListFilter.linkUnaryCallback),
            r'^-I.+$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-D.+$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-U.+$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-Wl,.+$' : (0, ArgumentListFilter.linkUnaryCallback),
            r'^-W(?!l,).*$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-f.+$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-std=.+$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-mtune=.+$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-print-prog-name=.*$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-print-file-name=.*$' : (0, ArgumentListFilter.compileUnaryCallback),
            
        }

        #iam: try and keep track of the files, input object, and output
        self.inputList = inputList
        self.inputFiles = []
        self.objectFiles = []
        self.outputFilename = None
        
        #iam: try and split the args into linker and compiler switches
        self.compileArgs = []
        self.linkArgs = []


        self.isVerbose = False
        self.isDependencyOnly = False
        self.isPreprocessOnly = False
        self.isAssembleOnly = False
        self.isAssembly = False
        self.isCompileOnly = False

        argExactMatches = dict(defaultArgExactMatches)
        argExactMatches.update(exactMatches)
        argPatterns = dict(defaultArgPatterns)
        argPatterns.update(patternMatches)

        self._inputArgs = collections.deque(inputList)

        #iam: parse the cmd line, bailing if we discover that there will be no second phase.
        while ( len(self._inputArgs) > 0   and
                not (self.isAssembly or
                     self.isAssembleOnly or
                     self.isPreprocessOnly  ) ):
            # Get the next argument
            currentItem = self._inputArgs.popleft()
            _logger.debug('Trying to match item ' + currentItem)
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
                    _logger.warning('Did not recognize the compiler flag "{0}"'.format(currentItem))
                    self.compileUnaryCallback(currentItem)

        if DUMPING:
            self.dump()

    def _shiftArgs(self, nargs):
        ret = []
        while nargs > 0:
            a = self._inputArgs.popleft()
            ret.append(a)
            nargs = nargs - 1
        return ret

    def abortUnaryCallback(self, flag):
        _logger.warning('Out of context experience: "{0}"'.format(str(self.inputList)))
        sys.exit(1)

    def inputFileCallback(self, infile):
        _logger.debug('Input file: ' + infile)
        self.inputFiles.append(infile)
        if re.search('\\.(s|S)$', infile):
            self.isAssembly = True

    def outputFileCallback(self, flag, filename):
        self.outputFilename = filename

    def objectFileCallback(self, objfile):
        self.objectFiles.append(objfile)

    def preprocessOnlyCallback(self, flag):
        self.isPreprocessOnly = True

    def dependencyOnlyCallback(self, flag):
        self.isDependencyOnly = True
        self.compileArgs.append(flag)

    def assembleOnlyCallback(self, flag):
        self.isAssembleOnly = True

    def verboseFlagCallback(self, flag):
        self.isVerbose = True

    def compileOnlyCallback(self, flag):
        self.isCompileOnly = True

    def linkUnaryCallback(self, flag):
        self.linkArgs.append(flag)

    def compileUnaryCallback(self, flag):
        self.compileArgs.append(flag)

    def darwinWarningLinkUnaryCallback(self, flag):
        if sys.platform.startswith('darwin'):
            _logger.warning('The flag "{0}" cannot be used with this tool'.format(flag))
            sys.exit(1)
        else:
            self.linkArgs.append(flag)

    def defaultBinaryCallback(self, flag, arg):
        _logger.warning('Ignoring compiler arg pair: "{0} {1}"'.format(flag, arg))

    def dependencyBinaryCallback(self, flag, arg):
        self.isDependencyOnly = True
        self.compileArgs.append(flag)
        self.compileArgs.append(arg)

    def compileBinaryCallback(self, flag, arg):
        self.compileArgs.append(flag)
        self.compileArgs.append(arg)


    def linkBinaryCallback(self, flag, arg):
        self.linkArgs.append(flag)
        self.linkArgs.append(arg)

    def getOutputFilename(self):
        if self.outputFilename is not None:
            return self.outputFilename
        elif self.isCompileOnly:
            #iam: -c but no -o, therefore the obj should end up in the cwd.
            (path, base) = os.path.split(self.inputFiles[0])
            (root, ext) = os.path.splitext(base)
            return '{0}.o'.format(root)
        else:
            return 'a.out'

    # iam: returns a pair [objectFilename, bitcodeFilename] i.e .o and .bc.
    # the hidden flag determines whether the objectFile is hidden like the
    # bitcodeFile is (starts with a '.'), use the logging level & DUMPING flag to get a sense
    # of what is being written out.
    def getArtifactNames(self, srcFile, hidden=False):
        (srcpath, srcbase) = os.path.split(srcFile)
        (srcroot, srcext) = os.path.splitext(srcbase)
        if hidden:
            objbase = '.{0}.o'.format(srcroot)
        else:
            objbase = '{0}.o'.format(srcroot)
        bcbase = '.{0}.o.bc'.format(srcroot)
        path = ''
        if self.outputFilename is not None:
            path = os.path.dirname(self.outputFilename)
        return [os.path.join(path, objbase), os.path.join(path, bcbase)]

    #iam: for printing our partitioning of the args
    def dump(self):
        _logger.debug('compileArgs: {0}'.format(self.compileArgs))
        _logger.debug('inputFiles: {0}'.format(self.inputFiles))
        _logger.debug('linkArgs: {0}'.format(self.linkArgs))
        _logger.debug('objectFiles: {0}'.format(self.objectFiles))
        _logger.debug('outputFilename: {0}'.format(self.outputFilename))
        for srcFile in self.inputFiles:
            _logger.debug('srcFile: {0}'.format(srcFile))
            (objFile, bcFile) = self.getArtifactNames(srcFile)
            _logger.debug('{0} ===> ({1}, {2})'.format(srcFile, objFile, bcFile))



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

      fileP = Popen(['file',os.path.realpath(fileName)], stdout=PIPE)
      output = fileP.communicate()[0]
      output = output.decode()
      if 'ELF' in output and 'executable' in output:
          return cls.ELF_EXECUTABLE
      if 'Mach-O' in output and 'executable' in output:
          return cls.MACH_EXECUTABLE
      elif 'ELF' in output and 'shared' in output:
          return cls.ELF_SHARED
      elif 'Mach-O' in output and 'dynamically linked shared' in output:
          return cls.MACH_SHARED
      elif 'current ar archive' in output:
          return cls.ARCHIVE
      elif 'ELF' in output and 'relocatable' in output:
          return cls.ELF_OBJECT
      elif 'Mach-O' in output and 'object' in output:
          return cls.MACH_OBJECT
      else:
          return cls.UNKNOWN

  @classmethod
  def init(cls):
      for (index, name) in enumerate(('UNKNOWN',
                                      'ELF_EXECUTABLE',
                                      'ELF_OBJECT',
                                      'ELF_SHARED',
                                      'MACH_EXECUTABLE',
                                      'MACH_OBJECT',
                                      'MACH_SHARED',
                                      'ARCHIVE')):
          setattr(cls, name, index)
          cls.revMap[index] = name

# Initialise FileType static class
FileType.init()

def attachBitcodePathToObject(bcPath, outFileName):
    # Don't try to attach a bitcode path to a binary.  Unfortunately
    # that won't work.
    (root, ext) = os.path.splitext(outFileName)
    _logger.debug('attachBitcodePathToObject: {0}  ===> {1} [ext = {2}]\n'.format(bcPath, outFileName, ext))
    #iam: this also looks very dodgey; we need a more reliable way to do this:
    if ext not in ('.o', '.lo', '.os', '.So', '.po'):
        _logger.warning('Cannot attach bitcode path to "{0} of type {1}"'.format(outFileName, FileType.getFileType(outFileName)))
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

    
    # Now write our bitcode section
    if (sys.platform.startswith('darwin')):
        objcopyCmd = ['ld', '-r', '-keep_private_externs', outFileName, '-sectcreate', darwinSegmentName, darwinSectionName,  f.name, '-o', outFileName]
    else:
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

    #clang and drogonegg share the same taste in bitcode filenames.
    def getBitcodeFileName(self, argFilter):
        (dirs, baseFile) = os.path.split(argFilter.getOutputFilename())
        bcfilename = os.path.join(dirs, '.{0}.bc'.format(baseFile))
        return bcfilename

class ClangBuilder(BuilderBase):
    def __init__(self, cmd, isCxx, prefixPath=None):
        super(ClangBuilder, self).__init__(cmd, isCxx, prefixPath)
        
    def getBitcodeCompiler(self):
        cc = self.getCompiler()
        return cc + ['-emit-llvm']

    def getCompiler(self):
        if self.isCxx:
            cxx =  os.getenv('LLVM_CXX_NAME')
            if cxx:
                return ['{0}{1}'.format(self.prefixPath, cxx)]
            else:
                return ['{0}clang++'.format(self.prefixPath)]
        else:
            cc =  os.getenv('LLVM_CC_NAME')
            if cc:
                return ['{0}{1}'.format(self.prefixPath, cc)]
            else:
                return ['{0}clang'.format(self.prefixPath)]

    def getBitcodeArglistFilter(self):
        return ClangBitcodeArgumentListFilter(self.cmd)

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
        # instead we want gcc to use our own assembler (see as.py).
        cmd = cc + ['-B', asDir, '-fplugin={0}'.format(pth), '-fplugin-arg-dragonegg-emit-ir']
        _logger.debug(cmd)
        return cmd

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

# This command does not have the executable with it
def buildAndAttachBitcode(builder):

    af = builder.getBitcodeArglistFilter()

    if ( len(af.inputFiles) == 0 or
         af.isAssembly or
         af.isAssembleOnly or
         (af.isDependencyOnly and not af.isCompileOnly) or
         af.isPreprocessOnly  ):
        _logger.debug('No work to do')
        _logger.debug(af.__dict__)
        return

    #iam: when we have multiple input files we'll have to keep track of their object files.
    newObjectFiles = []

    hidden = not af.isCompileOnly

    if  len(af.inputFiles) == 1 and af.isCompileOnly:
        # iam:
        # we could have
        # "... -c -o foo.o" or even "... -c -o foo.So" which is OK, but we could also have
        # "... -c -o crazy-assed.objectfile" which we wouldn't get right (yet)
        # so we need to be careful with the objFile and bcFile
        # maybe python-magic is in our future ...
        srcFile = af.inputFiles[0]
        (objFile, bcFile) = af.getArtifactNames(srcFile, hidden)
        if af.outputFilename is not None:
            objFile = af.outputFilename
            bcFile =  builder.getBitcodeFileName(af)
        buildBitcodeFile(builder, srcFile, bcFile)
        attachBitcodePathToObject(bcFile, objFile)

    else:

        for srcFile in af.inputFiles:
            (objFile, bcFile) = af.getArtifactNames(srcFile, hidden)
            if hidden:
                buildObjectFile(builder, srcFile, objFile)
                newObjectFiles.append(objFile)
            buildBitcodeFile(builder, srcFile, bcFile)
            attachBitcodePathToObject(bcFile, objFile)


    if not af.isCompileOnly:
        linkFiles(builder, newObjectFiles)

    sys.exit(0)

def linkFiles(builder, objectFiles):
    af = builder.getBitcodeArglistFilter()
    outputFile = af.getOutputFilename()
    cc = builder.getCompiler()
    cc.extend(objectFiles)
    cc.extend(af.objectFiles)
    cc.extend(af.linkArgs)
    cc.extend(['-o', outputFile])
    proc = Popen(cc)
    rc = proc.wait()
    if rc != 0:
        _logger.warning('Failed to link "{0}"'.format(str(cc)))
        sys.exit(rc)


def buildBitcodeFile(builder, srcFile, bcFile):
    af = builder.getBitcodeArglistFilter()
    bcc = builder.getBitcodeCompiler()
    bcc.extend(af.compileArgs)
    bcc.extend(['-c', srcFile])
    bcc.extend(['-o', bcFile])
    _logger.debug('buildBitcodeFile: {0}\n'.format(bcc))
    proc = Popen(bcc)
    rc = proc.wait()
    if rc != 0:
        _logger.warning('Failed to generate bitcode "{0}" for "{1}"'.format(bcFile, srcFile))
        sys.exit(rc)

def buildObjectFile(builder, srcFile, objFile):
    af = builder.getBitcodeArglistFilter()
    cc = builder.getCompiler()
    cc.extend(af.compileArgs)
    cc.append(srcFile)
    cc.extend(['-c', '-o',  objFile])
    _logger.debug('buildObjectFile: {0}\n'.format(cc))
    proc = Popen(cc)
    rc = proc.wait()
    if rc != 0:
        _logger.warning('Failed to generate object "{0}" for "{1}"'.format(objFile, srcFile))
        sys.exit(rc)

# bd & iam:
#
# case 1 (compileOnly):
#
# if the -c flag exists then so do all the .o files, and we need to
# locate them and produce and embed the bit code.
#
# locating them is easy:
#   either the .o is in the cmdline and we are in the simple case,
#   or else it was generated according to getObjectFilename
#
# we then produce and attach bitcode for each inputFile in the cmdline
#
#
# case 2 (compile and link)
#
#  af.inputFiles is not empty, and compileOnly is false.
#  in this case the .o's may not exist, we must regenerate
#  them in any case.
#
#
# case 3 (link only)
#
# in this case af.inputFiles is empty and we are done
#
#
