import logging
import collections
import os
import re

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
            '-gline-tables-only' : (0, ArgumentListFilter.compileUnaryCallback),

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

            # Code coverage instrumentation
            '-fprofile-arcs' : (0, ArgumentListFilter.compileLinkUnaryCallback),
            '-coverage' : (0, ArgumentListFilter.compileLinkUnaryCallback),

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
            r'^--sysroot=.+$' :  (0, ArgumentListFilter.compileUnaryCallback),
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

    #flags common to both linking and compiling (coverage for example)
    def compileLinkUnaryCallback(self, flag):
        self.compileArgs.append(flag)
        self.linkArgs.append(flag)

        
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



