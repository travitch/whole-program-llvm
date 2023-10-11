import logging
import collections
import os
import re
import sys

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
class ArgumentListFilter:
    def __init__(self, inputList, exactMatches={}, patternMatches={}):
        defaultArgExactMatches = {

            '-' : (0, ArgumentListFilter.standardInCallback),

            '-o' : (1, ArgumentListFilter.outputFileCallback),
            '-c' : (0, ArgumentListFilter.compileOnlyCallback),
            '-E' : (0, ArgumentListFilter.preprocessOnlyCallback),
            '-S' : (0, ArgumentListFilter.assembleOnlyCallback),

            '-v' : (0, ArgumentListFilter.verboseFlagCallback),
            '--verbose' : (0, ArgumentListFilter.verboseFlagCallback),
            '--param' : (1, ArgumentListFilter.compileBinaryCallback),
            '-aux-info' : (1, ArgumentListFilter.defaultBinaryCallback),

            #iam: presumably the len(inputFiles) == 0 in this case
            '--version' : (0, ArgumentListFilter.compileOnlyCallback),

            #warnings (apart from the regex below)
            '-w' : (0, ArgumentListFilter.compileUnaryCallback),
            '-W' : (0, ArgumentListFilter.compileUnaryCallback),


            #iam: if this happens, then we need to stop and think.
            '-emit-llvm' : (0, ArgumentListFilter.emitLLVMCallback),

            #iam: buildworld and buildkernel use these flags
            '-pipe' : (0, ArgumentListFilter.compileUnaryCallback),
            '-undef' : (0, ArgumentListFilter.compileUnaryCallback),
            '-nostdinc' : (0, ArgumentListFilter.compileUnaryCallback),
            '-nostdinc++' : (0, ArgumentListFilter.compileUnaryCallback),
            '-Qunused-arguments' : (0, ArgumentListFilter.compileUnaryCallback),
            '-no-integrated-as' : (0, ArgumentListFilter.compileUnaryCallback),
            '-integrated-as' : (0, ArgumentListFilter.compileUnaryCallback),
            #iam: gcc uses this in both compile and link, but clang only in compile
            #iam: actually on linux it looks to be both
            '-pthread' : (0, ArgumentListFilter.compileLinkUnaryCallback),
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
            '-m16': (0, ArgumentListFilter.compileLinkUnaryCallback),
            '-m32': (0, ArgumentListFilter.compileLinkUnaryCallback),
            '-mx32': (0, ArgumentListFilter.compileLinkUnaryCallback),
            '-m64': (0, ArgumentListFilter.compileLinkUnaryCallback),
            '-miamcu': (0, ArgumentListFilter.compileUnaryCallback),
            '-mstackrealign': (0, ArgumentListFilter.compileUnaryCallback),
            '-mretpoline-external-thunk': (0, ArgumentListFilter.compileUnaryCallback),  #iam: linux kernel stuff
            '-mno-fp-ret-in-387': (0, ArgumentListFilter.compileUnaryCallback),          #iam: linux kernel stuff
            '-mskip-rax-setup': (0, ArgumentListFilter.compileUnaryCallback),            #iam: linux kernel stuff
            '-mindirect-branch-register': (0, ArgumentListFilter.compileUnaryCallback),  #iam: linux kernel stuff
            # Preprocessor assertion
            '-A' : (1, ArgumentListFilter.compileBinaryCallback),
            '-D' : (1, ArgumentListFilter.compileBinaryCallback),
            '-U' : (1, ArgumentListFilter.compileBinaryCallback),

            '-arch' : (1, ArgumentListFilter.compileBinaryCallback),  #iam: openssl

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

            # Sysroot
            # Driver expands this into include options when compiling and
            # library options when linking
            '--sysroot' : (1, ArgumentListFilter.compileLinkBinaryCallback),

            # Architecture
            '-target' : (1, ArgumentListFilter.compileBinaryCallback),
            '-marm' : (0, ArgumentListFilter.compileUnaryCallback),

            # Language
            '-ansi' : (0, ArgumentListFilter.compileUnaryCallback),
            '-pedantic' : (0, ArgumentListFilter.compileUnaryCallback),
            #iam: i notice that yices configure passes -xc so
            # we should have a fall back pattern that captures the case
            # when there is no space between the x and the langauge.
            # for what its worth: the manual says the language can be one of
            # c  objective-c  c++ c-header  cpp-output  c++-cpp-output
            # assembler  assembler-with-cpp
            # BD: care to comment on your configure?

            '-x' : (1, ArgumentListFilter.compileBinaryCallback),

            # Debug
            '-g' : (0, ArgumentListFilter.compileUnaryCallback),
            '-g0' : (0, ArgumentListFilter.compileUnaryCallback),     #iam: clang not gcc
            '-ggdb' : (0, ArgumentListFilter.compileUnaryCallback),
            '-ggdb3' : (0, ArgumentListFilter.compileUnaryCallback),
            '-gdwarf-2' : (0, ArgumentListFilter.compileUnaryCallback),
            '-gdwarf-3' : (0, ArgumentListFilter.compileUnaryCallback),
            '-gdwarf-4' : (0, ArgumentListFilter.compileUnaryCallback),
            '-gline-tables-only' : (0, ArgumentListFilter.compileUnaryCallback),
            '-grecord-gcc-switches': (0, ArgumentListFilter.compileUnaryCallback),

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
            '-framework' : (1, ArgumentListFilter.linkBinaryCallback),

            # dragonegg mystery argument
            '--64' : (0, ArgumentListFilter.compileUnaryCallback),

            # binutils nonsense
            '-print-multi-directory' : (0, ArgumentListFilter.compileUnaryCallback),
            '-print-multi-lib' : (0, ArgumentListFilter.compileUnaryCallback),
            '-print-libgcc-file-name' : (0, ArgumentListFilter.compileUnaryCallback),

            # Code coverage instrumentation
            '-fprofile-arcs' : (0, ArgumentListFilter.compileLinkUnaryCallback),
            '-coverage' : (0, ArgumentListFilter.compileLinkUnaryCallback),
            '--coverage' : (0, ArgumentListFilter.compileLinkUnaryCallback),

            # ian's additions while building the linux kernel
            '/dev/null' : (0, ArgumentListFilter.inputFileCallback),
            '-mno-80387': (0, ArgumentListFilter.compileUnaryCallback), #gcc Don't generate output containing 80387 instructions for floating point.


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
            '-Wl,-dead_strip' :  (0, ArgumentListFilter.warningLinkUnaryCallback),
            '-dead_strip' :  (0, ArgumentListFilter.warningLinkUnaryCallback),
            '-Oz' : (0, ArgumentListFilter.compileUnaryCallback),   #did not find this in the GCC options.
            '-mno-global-merge' : (0, ArgumentListFilter.compileUnaryCallback),  #clang (do not merge globals)

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
            r'^.+\.(c|cc|cpp|C|cxx|i|s|S|bc)$' : (0, ArgumentListFilter.inputFileCallback),
            # FORTRAN file types
            r'^.+\.([fF](|[0-9][0-9]|or|OR|pp|PP))$' : (0, ArgumentListFilter.inputFileCallback),
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
            r'^-fsanitize=.+$' : (0, ArgumentListFilter.compileLinkUnaryCallback),
            r'^-f.+$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-rtlib=.+$' : (0, ArgumentListFilter.linkUnaryCallback),
            r'^-std=.+$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-stdlib=.+$' : (0, ArgumentListFilter.compileLinkUnaryCallback),
            r'^-mtune=.+$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-mstack-alignment=.+$': (0, ArgumentListFilter.compileUnaryCallback),                     #iam: linux kernel stuff
            r'^-mcmodel=.+$': (0, ArgumentListFilter.compileUnaryCallback),                              #iam: linux kernel stuff
            r'^-mpreferred-stack-boundary=.+$': (0, ArgumentListFilter.compileUnaryCallback),            #iam: linux kernel stuff
            r'^-mindirect-branch=.+$': (0, ArgumentListFilter.compileUnaryCallback),                     #iam: linux kernel stuff
            r'^-mregparm=.+$' : (0, ArgumentListFilter.compileUnaryCallback),                            #iam: linux kernel stuff
            r'^-march=.+$' : (0, ArgumentListFilter.compileUnaryCallback),                               #iam: linux kernel stuff
            r'^--param=.+$' : (0, ArgumentListFilter.compileUnaryCallback),                              #iam: linux kernel stuff


            #iam: mac stuff...
            r'-mmacosx-version-min=.+$' :  (0, ArgumentListFilter.compileUnaryCallback),

            r'^--sysroot=.+$' :  (0, ArgumentListFilter.compileUnaryCallback),
            r'^--gcc-toolchain=.+$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-print-prog-name=.*$' : (0, ArgumentListFilter.compileUnaryCallback),
            r'^-print-file-name=.*$' : (0, ArgumentListFilter.compileUnaryCallback),
            #iam: -xc from yices. why BD?
            r'^-x.+$' : (0, ArgumentListFilter.compileUnaryCallback),

        }

        #iam: try and keep track of the files, input object, and output
        self.inputList = inputList
        self.inputFiles = []
        self.objectFiles = []
        self.outputFilename = None

        #iam: try and split the args into linker and compiler switches
        self.compileArgs = []
        self.linkArgs = []
        # currently only dead_strip belongs here; but I guess there could be more.
        self.forbiddenArgs = []


        self.isVerbose = False
        self.isDependencyOnly = False
        self.isPreprocessOnly = False
        self.isAssembleOnly = False
        self.isAssembly = False
        self.isCompileOnly = False
        self.isEmitLLVM = False
        self.isStandardIn = False

        argExactMatches = dict(defaultArgExactMatches)
        argExactMatches.update(exactMatches)
        argPatterns = dict(defaultArgPatterns)
        argPatterns.update(patternMatches)

        self._inputArgs = collections.deque(inputList)

        #iam: parse the cmd line, bailing if we discover that there will be no second phase.
        while (self._inputArgs   and
               not (self.isAssembleOnly or
                    self.isPreprocessOnly)):
            # Get the next argument
            currentItem = self._inputArgs.popleft()
            _logger.debug('Trying to match item %s', currentItem)
            # First, see if this exact flag has a handler in the table.
            # This is a cheap test.  Otherwise, see if the input matches
            # some pattern with a handler that we recognize
            if currentItem in argExactMatches:
                (arity, handler) = argExactMatches[currentItem]
                flagArgs = self._shiftArgs(arity)
                handler(self, currentItem, *flagArgs)
            elif currentItem == '-Wl,--start-group':
                linkingGroup = [currentItem]
                terminated = False
                while self._inputArgs:
                    groupCurrent = self._inputArgs.popleft()
                    linkingGroup.append(groupCurrent)
                    if groupCurrent == "-Wl,--end-group":
                        terminated = True
                        break
                if not terminated:
                    _logger.warning('Did not find a closing "-Wl,--end-group" to match "-Wl,--start-group"')
                self.linkingGroupCallback(linkingGroup)
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
                    _logger.warning('Did not recognize the compiler flag "%s"', currentItem)
                    self.compileUnaryCallback(currentItem)

        if DUMPING:
            self.dump()


    def skipBitcodeGeneration(self):
        retval = (False, "")
        if os.environ.get('WLLVM_CONFIGURE_ONLY', False):
            retval = (True, "CFG Only")
        elif not self.inputFiles:
            retval = (True, "No input files")
        elif self.isEmitLLVM:
            retval = (True, "Emit LLVM")
        elif self.isAssembly or self.isAssembleOnly:
            retval = (True, "Assembly")
        elif self.isPreprocessOnly:
            retval = (True, "Preprocess Only")
        elif self.isStandardIn:
            retval = (True, "Standard In")
        elif (self.isDependencyOnly and not self.isCompileOnly):
            retval = (True, "Dependency Only")
        return retval

    def _shiftArgs(self, nargs):
        ret = []
        while nargs > 0:
            a = self._inputArgs.popleft()
            ret.append(a)
            nargs = nargs - 1
        return ret


    def standardInCallback(self, flag):
        _logger.debug('standardInCallback: %s', flag)
        self.isStandardIn = True

    def abortUnaryCallback(self, flag):
        _logger.warning('Out of context experience: "%s" "%s"', str(self.inputList), flag)
        sys.exit(1)

    def inputFileCallback(self, infile):
        _logger.debug('Input file: %s', infile)
        self.inputFiles.append(infile)
        if re.search('\\.(s|S)$', infile):
            self.isAssembly = True

    def outputFileCallback(self, flag, filename):
        _logger.debug('outputFileCallback: %s %s', flag, filename)
        self.outputFilename = filename

    def objectFileCallback(self, objfile):
        _logger.debug('objectFileCallback: %s', objfile)
        self.objectFiles.append(objfile)

    def preprocessOnlyCallback(self, flag):
        _logger.debug('preprocessOnlyCallback: %s', flag)
        self.isPreprocessOnly = True

    def dependencyOnlyCallback(self, flag):
        _logger.debug('dependencyOnlyCallback: %s', flag)
        self.isDependencyOnly = True
        self.compileArgs.append(flag)

    def assembleOnlyCallback(self, flag):
        _logger.debug('assembleOnlyCallback: %s', flag)
        self.isAssembleOnly = True

    def verboseFlagCallback(self, flag):
        _logger.debug('verboseFlagCallback: %s', flag)
        self.isVerbose = True

    def compileOnlyCallback(self, flag):
        _logger.debug('compileOnlyCallback: %s', flag)
        self.isCompileOnly = True

    def emitLLVMCallback(self, flag):
        _logger.debug('emitLLVMCallback: %s', flag)
        self.isEmitLLVM = True
        self.isCompileOnly = True

    def linkUnaryCallback(self, flag):
        _logger.debug('linkUnaryCallback: %s', flag)
        self.linkArgs.append(flag)

    def compileUnaryCallback(self, flag):
        _logger.debug('compileUnaryCallback: %s', flag)
        self.compileArgs.append(flag)

    def compileLinkUnaryCallback(self, flag):
        _logger.debug('compileLinkUnaryCallback: %s', flag)
        self.compileArgs.append(flag)
        self.linkArgs.append(flag)

    def warningLinkUnaryCallback(self, flag):
        _logger.debug('warningLinkUnaryCallback: %s', flag)
        _logger.warning('The flag "%s" cannot be used with this tool; we are ignoring it', flag)
        self.forbiddenArgs.append(flag)

    def defaultBinaryCallback(self, flag, arg):
        _logger.warning('Ignoring compiler arg pair: "%s %s"', flag, arg)

    def dependencyBinaryCallback(self, flag, arg):
        _logger.debug('dependencyBinaryCallback: %s %s', flag, arg)
        self.isDependencyOnly = True
        self.compileArgs.append(flag)
        self.compileArgs.append(arg)

    def compileBinaryCallback(self, flag, arg):
        _logger.debug('compileBinaryCallback: %s %s', flag, arg)
        self.compileArgs.append(flag)
        self.compileArgs.append(arg)

    def linkBinaryCallback(self, flag, arg):
        _logger.debug('linkBinaryCallback: %s %s', flag, arg)
        self.linkArgs.append(flag)
        self.linkArgs.append(arg)

    def compileLinkBinaryCallback(self, flag, arg):
        _logger.debug('compileLinkBinaryCallback: %s %s', flag, arg)
        self.compileArgs.append(flag)
        self.compileArgs.append(arg)
        self.linkArgs.append(flag)
        self.linkArgs.append(arg)

    def linkingGroupCallback(self, args):
        _logger.debug('linkingGroupCallback: %s', args)
        self.linkArgs.extend(args)

    def getOutputFilename(self):
        if self.outputFilename is not None:
            return self.outputFilename
        if self.isCompileOnly:
            #iam: -c but no -o, therefore the obj should end up in the cwd.
            (_, base) = os.path.split(self.inputFiles[0])
            (root, _) = os.path.splitext(base)
            return f'{root}.o'
        return 'a.out'

    def getBitcodeFileName(self):
        (dirs, baseFile) = os.path.split(self.getOutputFilename())
        bcfilename = os.path.join(dirs, f'.{baseFile}.bc')
        return bcfilename

    # iam: returns a pair [objectFilename, bitcodeFilename] i.e .o and .bc.
    # the hidden flag determines whether the objectFile is hidden like the
    # bitcodeFile is (starts with a '.'), use the logging level & DUMPING flag to get a sense
    # of what is being written out.
    def getArtifactNames(self, srcFile, hidden=False):
        (_, srcbase) = os.path.split(srcFile)
        (srcroot, _) = os.path.splitext(srcbase)
        if hidden:
            objbase = f'.{srcroot}.o'
        else:
            objbase = f'{srcroot}.o'
        bcbase = f'.{srcroot}.o.bc'
        return [objbase, bcbase]

    #iam: for printing our partitioning of the args
    def dump(self):
        efn = sys.stderr.write
        efn(f'\ncompileArgs: {self.compileArgs}\ninputFiles: {self.inputFiles}\nlinkArgs: {self.linkArgs}\n')
        efn(f'\nobjectFiles: {self.objectFiles}\noutputFilename: {self.outputFilename}\n')
        for srcFile in self.inputFiles:
            efn(f'\nsrcFile: {srcFile}\n')
            (objFile, bcFile) = self.getArtifactNames(srcFile)
            efn(f'\n{srcFile} ===> ({objFile}, {bcFile})\n')
        efn(f'\nFlags:\nisVerbose = {self.isVerbose}\n')
        efn(f'isDependencyOnly = {self.isDependencyOnly}\n')
        efn(f'isPreprocessOnly = {self.isPreprocessOnly}\n')
        efn(f'isAssembleOnly = {self.isAssembleOnly}\n')
        efn(f'isAssembly = {self.isAssembly}\n')
        efn(f'isCompileOnly = {self.isCompileOnly}\n')
        efn(f'isEmitLLVM = {self.isEmitLLVM}\n')
        efn(f'isStandardIn = {self.isStandardIn}\n')
