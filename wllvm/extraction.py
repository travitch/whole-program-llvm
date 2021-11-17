from __future__ import print_function

import os
import sys
import subprocess as sp
import re
import pprint
import tempfile
import shutil
import argparse
import codecs

from .popenwrapper import Popen

from .compilers import llvmCompilerPathEnv
from .compilers import elfSectionName
from .compilers import darwinSegmentName
from .compilers import darwinSectionName
from .compilers import getHashedPathName

from .filetype import FileType

from .logconfig import logConfig, informUser



_logger = logConfig(__name__)

decode_hex = codecs.getdecoder("hex_codec")

def extraction():
    """ This is the entry point to extract-bc.
    """

    (success, pArgs) = extract_bc_args()

    if not success:
        return 1

    if sys.platform.startswith('freebsd') or  sys.platform.startswith('linux'):
        return process_file_unix(pArgs)
    if sys.platform.startswith('darwin'):
        return process_file_darwin(pArgs)

    #iam: do we work on anything else?
    _logger.error('Unsupported or unrecognized platform: %s', sys.platform)
    return 1



bitCodeArchiveExtension = 'bca'
moduleExtension = 'bc'

# Environmental variable for cross-compilation target.
binutilsTargetPrefixEnv = 'BINUTILS_TARGET_PREFIX'

def getSectionSizeAndOffset(sectionName, filename):
    """Returns the size and offset of the section, both in bytes.

    Use objdump on the provided binary; parse out the fields
    to find the given section.  Parses the output,and
    extracts thesize and offset of that section (in bytes).
    """

    binUtilsTargetPrefix = os.getenv(binutilsTargetPrefixEnv)
    objdumpBin = f'{binUtilsTargetPrefix}-{"objdump"}' if binUtilsTargetPrefix else 'objdump'
    objdumpCmd = [objdumpBin, '-h', '-w', filename]
    objdumpProc = Popen(objdumpCmd, stdout=sp.PIPE)

    objdumpOutput = objdumpProc.communicate()[0]
    if objdumpProc.returncode != 0:
        _logger.error('Could not dump %s', filename)
        sys.exit(-1)

    for line in [l.decode('utf-8') for l in objdumpOutput.splitlines()]:
        fields = line.split()
        if len(fields) <= 7:
            continue
        if fields[1] != sectionName:
            continue
        try:
            size = int(fields[2], 16)
            offset = int(fields[5], 16)
            return (size, offset)
        except ValueError:
            continue

    # The needed section could not be found
    _logger.warning('Could not find "%s" ELF section in "%s", so skipping this entry.', sectionName, filename)
    return None

def getSectionContent(size, offset, filename):
    """Reads the entire content of an ELF section into a string."""
    with open(filename, mode='rb') as f:
        f.seek(offset)
        d = ''
        try:
            c = f.read(size)
            d = c.decode('utf-8')
        except UnicodeDecodeError:
            _logger.error('Failed to read section containing:')
            print(c)
            raise
        # The linker pads sections with null bytes; our real data
        # cannot have null bytes because it is just text.  Discard
        # nulls.
        return d.replace('\0', '')


# otool hexdata pattern.
otool_hexdata = re.compile(r'^(?:[0-9a-f]{8,16}\t)?([0-9a-f\s]+)$', re.IGNORECASE)

#iam: 04/09/2021
def convert2octects(otooln):
    """Converts a otool output line into a list of octets.

    The otool output format varies between Intel and M1 chips.

    Intel:
    0000000000000070	2f 55 73 65 72 73 2f 65 32 37 36 35 38 2f 52 65

    M1:
    000000010000c000	6573552f 692f7372 522f6d61 736f7065

    The input string corresponds to substring after the tab that follows
    tthe starting address.

    """
    octets = []
    chunks = otooln.split()
    for chunk in chunks:
        if len(chunk) == 2:
            octets.append(chunk)
        else:
          twoples = [chunk[i:i+2] for i in range(0, len(chunk), 2)]
          twoples.reverse()
          octets.extend(twoples)
    return octets

def extract_section_darwin(inputFile):
    """Extracts the section as a string, the darwin version.

    Uses otool to extract the section, then processes it
    to a usable state.

    iam: 04/09/2021  Using otool here is starting to be a real pain.
    The output format varies between XCode versions, and also between Intel and M1
    chips.
    """
    retval = None

    otoolCmd = ['otool', '-X', '-s', darwinSegmentName, darwinSectionName, inputFile]
    otoolProc = Popen(otoolCmd, stdout=sp.PIPE)

    otoolOutput = otoolProc.communicate()[0]
    if otoolProc.returncode != 0:
        _logger.error('otool failed on %s', inputFile)
        sys.exit(-1)

    lines = otoolOutput.decode('utf8').splitlines()
    _logger.debug('otool extracted:\n%s\n', lines)
    # iam 03/06/2021: so otool prior to llvm-otool(1): Apple Inc. version cctools-977.1
    # would output 'Contents of (__WLLVM,__llvm_bc) section' as the first line
    # of the extraction. This seems to have disappeared so we need to be careful
    # here:
    if lines and lines[0] and lines[0].startswith('Contents'):
        _logger.debug('dropping header: "%s"', lines[0])
        lines = lines[1:]
    try:
        octets = []
        for line in lines:
            m = otool_hexdata.match(line)
            if not m:
                _logger.debug('otool output:\n\t%s\nDID NOT match expectations.', line)
                continue
            octetline = m.group(1)
            octets.extend(convert2octects(octetline))
        _logger.debug('We parsed this as:\n%s', octets)
        retval = decode_hex(''.join(octets))[0].splitlines()
        # these have become bytes in the "evolution" of python
        retval = [ f.decode('utf8') for f in retval]
        _logger.debug('decoded:\n%s\n', retval)
        if not retval:
            _logger.error('%s contained no %s segment', inputFile, darwinSegmentName)
    except Exception as e:
        _logger.error('extract_section_darwin: %s', str(e))
    return retval

def extract_section_linux(inputFile):
    """Extracts the section as a string, the *nix version."""
    val = getSectionSizeAndOffset(elfSectionName, inputFile)
    if val is None:
        return []
    (sectionSize, sectionOffset) = val
    content = getSectionContent(sectionSize, sectionOffset, inputFile)
    contents = content.split('\n')
    if not contents:
        _logger.error('%s contained no %s. section is empty', inputFile, elfSectionName)
    return contents


def getStorePath(bcPath):
    storeEnv = os.getenv('WLLVM_BC_STORE')
    if storeEnv:
        hashName = getHashedPathName(bcPath)
        hashPath = os.path.join(storeEnv, hashName)
        if os.path.isfile(hashPath):
            return hashPath
    return None


def getBitcodePath(bcPath):
    """Tries to resolve the whereabouts of the bitcode.

    First, checks if the given path points to an existing bitcode file.
    If it does not, it tries to look for the bitcode file in the store directory given
    by the environment variable WLLVM_BC_STORE.
    """

    if not bcPath or os.path.isfile(bcPath):
        return bcPath

    storePath = getStorePath(bcPath)
    if storePath:
        return storePath
    return bcPath

def executeLinker(linkCmd):
    try:
        # Use blocking call here since the output file needs to be generated
        # before we can continue linking.
        exitCode = sp.check_call(linkCmd)
    except OSError as e:
        if e.errno == 2:
            errorMsg = 'Your llvm-link does not seem to be easy to find.\nEither install it or use the -l llvmLinker option.'
        else:
            errorMsg = f'OS error({e.errno}): {e.strerror}'
        _logger.error(errorMsg)
        raise Exception(errorMsg) from e

    return exitCode

def incrementallyLinkFiles(pArgs, fileNames):
    linkCmd = [pArgs.llvmLinker, '-v'] if pArgs.verboseFlag else [pArgs.llvmLinker]

    linkCmd.append(f'-o={pArgs.outputFile}')

    # fileNames has already been adjusted and checked in function linkFiles.
    first, remaining = fileNames[0], fileNames[1:]
    linkCmd.append(first)

    exitCode = executeLinker(linkCmd)

    # Use the output file as part of the next linking process to overwrite
    # it incrementally.
    linkCmd.append(pArgs.outputFile)

    for bc_file in remaining:
        # Adjust the previously first file path and link remaining files.
        # The linking process has to be done with blocking calls here too
        # since we are overwriting the file completely everytime.
        linkCmd[len(linkCmd) - 2] = bc_file
        exitCode = executeLinker(linkCmd)

    _logger.info('%s returned %s', pArgs.llvmLinker, str(exitCode))

    return exitCode


def linkFiles(pArgs, fileNames):
    linkCmd = [pArgs.llvmLinker, '-v'] if pArgs.verboseFlag else [pArgs.llvmLinker]

    linkCmd.append(f'-o={pArgs.outputFile}')

    fileNames = map(getBitcodePath, fileNames)
    fileNames = [x for x in fileNames if x != '']

    # Check the size of the argument string first: If it is larger than the
    # allowed size specified by 'getconf ARG_MAX' we have to link the files
    # incrementally to avoid weird errors.
    arg_max = int(sp.getoutput('getconf ARG_MAX'))
    str_len = sum([len(x) for x in fileNames])
    if str_len > arg_max:
        return incrementallyLinkFiles(pArgs, fileNames)

    linkCmd.extend(fileNames)
    
    exitCode = executeLinker(linkCmd)
    _logger.info('%s returned %s', pArgs.llvmLinker, str(exitCode))
    return exitCode


def archiveFiles(pArgs, fileNames):
    retCode = 0
    # We do not want full paths in the archive so we need to chdir into each
    # bitcode's folder. Handle this by calling llvm-ar once for all bitcode
    # files in the same directory

    # Map of directory names to list of bitcode files in that directory
    dirToBCMap = {}
    for bitCodeFile in fileNames:
        dirName = os.path.dirname(bitCodeFile)
        basename = os.path.basename(bitCodeFile)
        if dirName in dirToBCMap:
            dirToBCMap[dirName].append(basename)
        else:
            dirToBCMap[dirName] = [basename]

    _logger.debug('Built up directory to bitcode file list map:\n%s', pprint.pformat(dirToBCMap))

    for (dirname, bcList) in dirToBCMap.items():
        _logger.debug('Changing directory to "%s"', dirname)
        os.chdir(dirname)
        larCmd = [pArgs.llvmArchiver, 'rs', pArgs.outputFile] + bcList
        larProc = Popen(larCmd)
        retCode = larProc.wait()
        if retCode != 0:
            _logger.error('Failed to execute:\n%s', pprint.pformat(larCmd))
            break

    if retCode == 0:
        informUser(f'Generated LLVM bitcode archive {pArgs.outputFile}\n')
    else:
        _logger.error('Failed to generate LLVM bitcode archive')

    return retCode

def extract_from_thin_archive(inputFile):
    """Extracts the paths from the thin archive.

    """
    retval = None

    arCmd = ['ar', '-t', inputFile]         #iam: check if this might be os dependent
    arProc = Popen(arCmd, stdout=sp.PIPE)

    arOutput = arProc.communicate()[0]
    if arProc.returncode != 0:
        _logger.error('ar failed on %s', inputFile)
    else:
        retval = arOutput.splitlines()
    return retval



def handleExecutable(pArgs):

    fileNames = pArgs.extractor(pArgs.inputFile)

    if not fileNames:
        return 1

    if  pArgs.sortBitcodeFilesFlag:
        fileNames = sorted(fileNames)


    if pArgs.manifestFlag:
        writeManifest(f'{pArgs.inputFile}.llvm.manifest', fileNames)

    if pArgs.outputFile is None:
        pArgs.outputFile = f'{pArgs.inputFile}.{moduleExtension}'

    return linkFiles(pArgs, fileNames)


def handleThinArchive(pArgs):

    objectPaths = extract_from_thin_archive(pArgs.inputFile)

    if not objectPaths:
        return 1

    bcFiles = []
    for p in objectPaths:
        _logger.debug('handleThinArchive: processing %s', p)
        contents = pArgs.extractor(p)
        for c in contents:
            if c:
                _logger.debug('\t including %s', c)
                bcFiles.append(str(c))



    return  buildArchive(pArgs, bcFiles)

#iam: do we want to preserve the order in the archive? if so we need to return both the list and the dict.
def fetchTOC(inputFile):
    toc = {}

    arCmd = ['ar', '-t', inputFile]         #iam: check if this might be os dependent
    arProc = Popen(arCmd, stdout=sp.PIPE)

    arOutput = arProc.communicate()[0]
    if arProc.returncode != 0:
        _logger.error('ar failed on %s', inputFile)
        return toc

    lines = arOutput.splitlines()

    for line in lines:
        if line in toc:
            toc[line] += 1
        else:
            toc[line] = 1

    return toc


def extractFile(archive, filename, instance):
    arCmd = ['ar', 'xN', str(instance), archive, filename]         #iam: check if this might be os dependent
    try:
        arP = Popen(arCmd)
    except Exception as e:
        _logger.error(e)
        return False

    arPE = arP.wait()

    if arPE != 0:
        errorMsg = f'Failed to execute archiver with command {arCmd}'
        _logger.error(errorMsg)
        return False

    return True



def handleArchiveDarwin(pArgs):
    originalDir = os.getcwd() # This will be the destination

    pArgs.arCmd.append(pArgs.inputFile)

    # Make temporary directory to extract objects to
    tempDir = ''
    bitCodeFiles = []

    try:


        tempDir = tempfile.mkdtemp(suffix='wllvm')
        os.chdir(tempDir)

        # Extract objects from archive
        try:
            arP = Popen(pArgs.arCmd)
        except OSError as e:
            if e.errno == 2:
                errorMsg = 'Your ar does not seem to be easy to find.\n'
            else:
                errorMsg = f'OS error({e.errno}): {e.strerror}'
            _logger.error(errorMsg)
            raise Exception(errorMsg) from e

        arPE = arP.wait()

        if arPE != 0:
            errorMsg = f'Failed to execute archiver with command {pArgs.arCmd}'
            _logger.error(errorMsg)
            raise Exception(errorMsg)

        _logger.debug(2)

        # Iterate over objects and examine their bitcode inserts
        for (root, _, files) in os.walk(tempDir):
            _logger.debug('Exploring "%s"', root)
            for f in files:
                fPath = os.path.join(root, f)
                if FileType.getFileType(fPath) == pArgs.fileType:

                    # Extract bitcode locations from object
                    contents = pArgs.extractor(fPath)

                    for bcFile in contents:
                        if bcFile != '':
                            if not os.path.exists(bcFile):
                                _logger.warning('%s lists bitcode library "%s" but it could not be found', f, bcFile)
                            else:
                                bitCodeFiles.append(bcFile)
                else:
                    _logger.info('Ignoring file "%s" in archive', f)

        _logger.info('Found the following bitcode file names to build bitcode archive:\n%s', pprint.pformat(bitCodeFiles))

    finally:
        # Delete the temporary folder
        _logger.debug('Deleting temporary folder "%s"', tempDir)
        shutil.rmtree(tempDir)

    #write the manifest file if asked for
    if pArgs.manifestFlag:
        writeManifest(f'{pArgs.inputFile}.llvm.manifest', bitCodeFiles)

    # Build bitcode archive
    os.chdir(originalDir)

    return buildArchive(pArgs, bitCodeFiles)



#iam: 5/1/2018
def handleArchiveLinux(pArgs):
    """ handleArchiveLinux processes a archive, and creates either a bitcode archive, or a module, depending on the flags used.

    Archives on Linux are strange beasts. handleArchive processes the archive by:

      1. first creating a table of contents of the archive, which maps file names (in the archive) to the number of
    times a file with that name is stored in the archive.

      2. for each OCCURENCE of a file (name and count) it extracts the section from the object file, and adds the
    bitcode paths to the bitcode list.

      3. it then either links all these bitcode files together using llvm-link,  or else is creates a bitcode
    archive using llvm-ar

    """

    inputFile = pArgs.inputFile

    originalDir = os.getcwd() # We want to end up back where we started.

    toc = fetchTOC(inputFile)

    if not toc:
        _logger.warning('No files found, so nothing to be done.')
        return 0

    bitCodeFiles = []

    try:
        tempDir = tempfile.mkdtemp(suffix='wllvm')
        os.chdir(tempDir)

        for filename in toc:
            count = toc[filename]
            for i in range(1, count + 1):

                # extact out the ith instance of filename
                if extractFile(inputFile, filename, i):
                    # Extract bitcode locations from object
                    contents = pArgs.extractor(filename)
                    _logger.debug('From instance %s of %s in %s we extracted\n\t%s\n', i, filename, inputFile, contents)
                    if contents:
                        for path in contents:
                            if path:
                                bitCodeFiles.append(path)
                    else:
                        _logger.debug('From instance %s of %s in %s we extracted NOTHING\n', i, filename, inputFile)

    finally:
        # Delete the temporary folder
        _logger.debug('Deleting temporary folder "%s"', tempDir)
        shutil.rmtree(tempDir)

    _logger.debug('From instance %s we extracted\n\t%s\n', inputFile, bitCodeFiles)

    # Build bitcode archive
    os.chdir(originalDir)

    return buildArchive(pArgs, bitCodeFiles)






def buildArchive(pArgs, bitCodeFiles):

    if pArgs.bitcodeModuleFlag:
        _logger.info('Generating LLVM Bitcode module from an archive')
    else:
        _logger.info('Generating LLVM Bitcode archive from an archive')

    if  pArgs.sortBitcodeFilesFlag:
        bitCodeFiles = sorted(bitCodeFiles)

    #write the manifest file if asked for
    if pArgs.manifestFlag:
        writeManifest(f'{pArgs.inputFile}.llvm.manifest', bitCodeFiles)

    if pArgs.bitcodeModuleFlag:

        # Pick output file path if outputFile not set
        if pArgs.outputFile is None:
            pArgs.outputFile = pArgs.inputFile
            pArgs.outputFile += '.' + moduleExtension

        informUser(f'Writing output to {pArgs.outputFile}\n')
        return linkFiles(pArgs, bitCodeFiles)

    # Pick output file path if outputFile not set
    if pArgs.outputFile is None:
        bcaExtension = '.' + bitCodeArchiveExtension
        if pArgs.inputFile.endswith('.a'):
            # Strip off .a suffix
            pArgs.outputFile = pArgs.inputFile[:-2]
            pArgs.outputFile += bcaExtension
        else:
            pArgs.outputFile = pArgs.inputFile + bcaExtension

    informUser(f'Writing output to {pArgs.outputFile}\n')
    return archiveFiles(pArgs, bitCodeFiles)


def writeManifest(manifestFile, bitCodeFiles):
    with open(manifestFile, 'w') as output:
        for f in bitCodeFiles:
            output.write(f'{f}\n')
            sf = getStorePath(f)
            if sf:
                output.write(f'{sf}\n')
    _logger.warning('Manifest written to %s', manifestFile)



class ExtractedArgs:

    def __init__(self):
        self.fileType = None
        self.outputFile = None
        self.inputFile = None
        self.output = None
        self.extractor = None
        self.arCmd = None


def extract_bc_args():

    # do we need a path in front?
    llvmToolPrefix = os.getenv(llvmCompilerPathEnv)
    if not llvmToolPrefix:
        llvmToolPrefix = ''

    # is our linker called something different?
    llvmLinkerName = os.getenv('LLVM_LINK_NAME')
    if not llvmLinkerName:
        llvmLinkerName = 'llvm-link'
    llvmLinker = os.path.join(llvmToolPrefix, llvmLinkerName)

    # is our archiver called something different?
    llvmArchiverName = os.getenv('LLVM_AR_NAME')
    if not llvmArchiverName:
        llvmArchiverName = 'llvm-ar'
    llvmArchiver = os.path.join(llvmToolPrefix, llvmArchiverName)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(dest='inputFile',
                        help='A binary produced by wllvm/wllvm++')
    parser.add_argument('--linker', '-l',
                        dest='llvmLinker',
                        help='The LLVM bitcode linker to use. Default "%(default)s"',
                        default=llvmLinker)
    parser.add_argument('--archiver', '-a',
                        dest='llvmArchiver',
                        help='The LLVM bitcode archiver to use. Default "%(default)s"',
                        default=llvmArchiver)
    parser.add_argument('--verbose', '-v',
                        dest='verboseFlag',
                        help='Call the external procedures in verbose mode.',
                        action="store_true")
    parser.add_argument('--manifest', '-m',
                        dest='manifestFlag',
                        help='Write a manifest file listing all the .bc files used.',
                        action='store_true')
    parser.add_argument('--sort', '-s',
                        dest='sortBitcodeFilesFlag',
                        help='Sort the list of bitcode files (for debugging).',
                        action='store_true')
    parser.add_argument('--bitcode', '-b',
                        dest='bitcodeModuleFlag',
                        help='Extract a bitcode module rather than an archive. ' +
                        'Only useful when extracting from an archive.',
                        action='store_true')
    parser.add_argument('--output', '-o',
                        dest='outputFile',
                        help='The output file. Defaults to a file in the same directory ' +
                        'as the input with the same name as the input but with an ' +
                        'added file extension (.'+ moduleExtension + ' for bitcode '+
                        'modules and .' + bitCodeArchiveExtension +' for bitcode archives)',
                        default=None)
    pArgs = parser.parse_args(namespace=ExtractedArgs())


    # Check file exists
    if not os.path.exists(pArgs.inputFile):
        _logger.error('File "%s" does not exist.', pArgs.inputFile)
        return (False, None)

    pArgs.inputFile = os.path.abspath(pArgs.inputFile)


    # Check output destitionation if set
    outputFile = pArgs.outputFile
    if outputFile is not None:
        # Get Absolute output path
        outputFile = os.path.abspath(outputFile)
        if not os.path.exists(os.path.dirname(outputFile)):
            _logger.error('Output directory "%s" does not exist.', os.path.dirname(outputFile))
            return (False, None)

    pArgs.output = outputFile

    return (True, pArgs)




def process_file_unix(pArgs):
    retval = 1
    ft = FileType.getFileType(pArgs.inputFile)
    _logger.debug('Detected file type is %s', FileType.revMap[ft])

    pArgs.arCmd = ['ar', 'xv'] if pArgs.verboseFlag else ['ar', 'x']
    pArgs.extractor = extract_section_linux
    pArgs.fileType = FileType.ELF_OBJECT

    if ft in (FileType.ELF_EXECUTABLE, FileType.ELF_SHARED, FileType.ELF_OBJECT):
        _logger.info('Generating LLVM Bitcode module')
        retval = handleExecutable(pArgs)
    elif ft == FileType.ARCHIVE:
        retval = handleArchiveLinux(pArgs)
    elif ft == FileType.THIN_ARCHIVE:
        retval = handleThinArchive(pArgs)
    else:
        _logger.error('File "%s" of type %s cannot be used', pArgs.inputFile, FileType.revMap[ft])
    return retval



def process_file_darwin(pArgs):
    retval = 1
    ft = FileType.getFileType(pArgs.inputFile)
    _logger.debug('Detected file type is %s', FileType.revMap[ft])

    pArgs.arCmd = ['ar', '-x', '-v'] if pArgs.verboseFlag else ['ar', '-x']
    pArgs.extractor = extract_section_darwin
    pArgs.fileType = FileType.MACH_OBJECT

    if ft in (FileType.MACH_EXECUTABLE, FileType.MACH_SHARED, FileType.MACH_OBJECT):
        _logger.info('Generating LLVM Bitcode module')
        retval = handleExecutable(pArgs)
    elif ft == FileType.ARCHIVE:
        _logger.info('Handling archive')
        retval = handleArchiveDarwin(pArgs)


    else:
        _logger.error('File "%s" of type %s cannot be used', pArgs.inputFile, FileType.revMap[ft])
    return retval
