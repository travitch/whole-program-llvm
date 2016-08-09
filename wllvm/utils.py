from __future__ import absolute_import
from __future__ import print_function

from subprocess import *
import pprint
import logging
import errno
import os
import sys
import tempfile

from .filetype import FileType
from .popenwrapper import Popen
from .arglistfilter import ArgumentListFilter

# Internal logger
_logger = logging.getLogger(__name__)


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


# Same as an ArgumentListFilter, but DO NOT change the name of the output filename when
# building the bitcode file so that we don't clobber the object file.
class ClangBitcodeArgumentListFilter(ArgumentListFilter):
    def __init__(self, arglist):
        localCallbacks = { '-o' : (1, ClangBitcodeArgumentListFilter.outputFileCallback) }
        super(ClangBitcodeArgumentListFilter, self).__init__(arglist, exactMatches=localCallbacks)

    def outputFileCallback(self, flag, filename):
        self.outputFilename = filename



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
    _logger.debug('buildObject rc = {0}'.format(rc))
    return rc


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
        _logger.debug('Compile only case: {0}'.format(af.inputFiles[0]))
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
