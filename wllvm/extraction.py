import os
import sys
import subprocess as sp
import re

from .popenwrapper import Popen

from .compilers import llvmCompilerPathEnv
from .compilers import elfSectionName
from .compilers import darwinSegmentName
from .compilers import darwinSectionName

from .filetype import FileType

from .logconfig import *

import logging
import pprint
import tempfile
import shutil
import argparse

"""
(Fix: 2016/02/16: __LLVM is now used by MacOS's ld so we changed the segment name to __WLLVM).

"""



# Python 2 does not have exceptions automatically
# imported whereas python 3 does. Handle this
try:
    dir(UnicodeDecodeError)
except NameError:
  import exceptions

bitCodeArchiveExtension='bca'
moduleExtension='bc'

def getSectionSizeAndOffset(sectionName, filename):
    """Returns the size and offset of the section, both in bytes.

    Use objdump on the provided binary; parse out the fields
    to find the given section.  Parses the output,and
    extracts thesize and offset of that section (in bytes).
    """
    objdumpCmd = ['objdump', '-h', '-w', filename]
    objdumpProc = Popen(objdumpCmd, stdout=sp.PIPE)

    objdumpOutput = objdumpProc.communicate()[0]
    if objdumpProc.returncode != 0:
        logging.error('Could not dump %s' % filename)
        sys.exit(-1)

    for line in [l.decode('utf-8') for l in objdumpOutput.splitlines()] :
        fields = line.split()
        if len(fields) <= 7:
            continue
        if fields[1] != sectionName:
            continue
        try:
            idx = int(fields[0])
            size = int(fields[2], 16)
            offset = int(fields[5], 16)
            return (size, offset)
        except ValueError:
            continue

    # The needed section could not be found
    logging.warning('Could not find "{0}" ELF section in "{1}", so skipping this entry.'.format(sectionName,filename))
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
            logging.error('Failed to read section containing:')
            print(c)
            raise
        # The linker pads sections with null bytes; our real data
        # cannot have null bytes because it is just text.  Discard
        # nulls.
        return d.replace('\0', '')


"""
otool hexdata pattern. 
"""
otool_hexdata = re.compile('^(?:[0-9a-f]{8,16}\t)?([0-9a-f\s]+)$', re.IGNORECASE)


def extract_section_darwin(inputFile):
    """Extracts the section as a string, the darwin version.

    Uses otool to extract the section, then processes it
    to a usable state.

    """
    retval = None
    
    otoolCmd  = ['otool', '-X', '-s', darwinSegmentName, darwinSectionName, inputFile]
    otoolProc = Popen(otoolCmd, stdout=sp.PIPE)

    otoolOutput = otoolProc.communicate()[0]
    if otoolProc.returncode != 0:
        logging.error('otool failed on %s' % inputFile)
        sys.exit(-1)

    lines = otoolOutput.splitlines()

    try:
        octets = []
        for line in lines:
            m = otool_hexdata.match(line)
            if not m:
                logging.debug('otool output:\n\t{0}\nDID NOT match expectations.'.format(line))
                continue
            octetline = m.group(1)
            octets.extend(octetline.split())
        octets = ''.join(octets)
        retval = octets.decode('hex').splitlines()
        if not retval:
            logging.error('{0} contained no {1} segment'.format(inputFile, darwinSegmentName))
    except Exception as e:
        logging.error('extract_section_darwin: {0}'.format(str(e)))
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
        logging.error('{0} contained no {1} section is empty'.format(inputFile, elfSectionName))
    return contents


def linkFiles(pArgs, fileNames):
    linkCmd = [ pArgs.llvmLinker, '-v' ] if pArgs.verboseFlag else [ pArgs.llvmLinker ]

    linkCmd.extend(['-o', pArgs.outputFile ])

    linkCmd.extend([x for x in fileNames if x != ''])
    logging.info('Writing output to {0}'.format(pArgs.outputFile))
    try:
        linkProc = Popen(linkCmd)
    except OSError as e:
        if e.errno == 2:
            errorMsg = 'Your llvm-link does not seem to be easy to find.\nEither install it or use the -l llvmLinker option.'
        else:
            errorMsg = 'OS error({0}): {1}'.format(e.errno, e.strerror)
        logging.error(errorMsg)
        raise Exception(errorMsg)

    else:
        exitCode = linkProc.wait()
        logging.info('{0} returned {1}'.format(pArgs.llvmLinker, str(exitCode)))
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
            dirToBCMap[dirName] = [ basename ]

    logging.debug('Built up directory to bitcode file list map:\n{0}'.format(
                   pprint.pformat(dirToBCMap)))

    for (dirname, bcList) in dirToBCMap.items():
        logging.debug('Changing directory to "{0}"'.format(dirname))
        os.chdir(dirname)
        larCmd = [pArgs.llvmArchiver, 'rs', pArgs.outputFile ] + bcList
        larProc = Popen(larCmd)
        retCode = larProc.wait()
        if retCode != 0:
          logging.error('Failed to execute:\n{0}'.format(pprint.pformat(larCmd)))
          break

    if retCode == 0:
        logging.info('Generated LLVM bitcode archive {0}'.format(pArgs.outputFile))
    else:
        logging.error('Failed to generate LLVM bitcode archive')

    return retCode


def handleExecutable(pArgs):

    fileNames = pArgs.extractor(pArgs.inputFile)

    if not fileNames:
        return 1

    if pArgs.manifestFlag:
        manifestFile = '{0}.llvm.manifest'.format(pArgs.inputFile)
        with open(manifestFile, 'w') as output:
            for f in fileNames:
                output.write('{0}\n'.format(f))

    if pArgs.outputFile == None:
        pArgs.outputFile = pArgs.inputFile + '.' + moduleExtension

    return linkFiles(pArgs, fileNames)




def handleArchive(pArgs):

    originalDir = os.getcwd() # This will be the destination

    pArgs.arCmd.append(pArgs.inputFile)

    # Make temporary directory to extract objects to
    tempDir = ''
    bitCodeFiles = [ ]
    retCode=0
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
                errorMsg = 'OS error({0}): {1}'.format(e.errno, e.strerror)
            logging.error(errorMsg)
            raise Exception(errorMsg)

        arPE = arP.wait()

        if arPE != 0:
            errorMsg = 'Failed to execute archiver with command {0}'.format(pArgs.arCmd)
            logging.error(errorMsg)
            raise Exception(errorMsg)

        # Iterate over objects and examine their bitcode inserts
        for (root, dirs, files) in os.walk(tempDir):
           logging.debug('Exploring "{0}"'.format(root))
           for f in files:
               fPath = os.path.join(root, f)
               if FileType.getFileType(fPath) == pArgs.fileType:

                   # Extract bitcode locations from object
                   contents = pArgs.extractor(fPath)

                   for bcFile in contents:
                       if bcFile != '':
                           if not os.path.exists(bcFile):
                               logging.warning('{0} lists bitcode library "{1}" but it could not be found'.format(f, bcFile))
                           else:
                               bitCodeFiles.append(bcFile)
               else:
                   logging.info('Ignoring file "{0}" in archive'.format(f))

        logging.info('Found the following bitcode file names to build bitcode archive:\n{0}'.format(
            pprint.pformat(bitCodeFiles)))

    finally:
        # Delete the temporary folder
        logging.debug('Deleting temporary folder "{0}"'.format(tempDir))
        shutil.rmtree(tempDir)

    #write the manifest file if asked for
    if pArgs.manifestFlag:
        manifestFile = '{0}.llvm.manifest'.format(pArgs.inputFile)
        with open(manifestFile, 'w') as output:
            for f in bitCodeFiles:
                output.write('{0}\n'.format(f))

    # Build bitcode archive
    os.chdir(originalDir)

    return buildArchive(pArgs, bitCodeFiles)

def buildArchive(pArgs, bitCodeFiles):

    if pArgs.bitcodeModuleFlag:

        # Pick output file path if outputFile not set
        if pArgs.outputFile == None:
            pArgs.outputFile = pArgs.inputFile
            pArgs.outputFile += '.' + moduleExtension

        logging.info('Writing output to {0}'.format(pArgs.outputFile))

        return linkFiles(pArgs, bitCodeFiles)

    else:

        # Pick output file path if outputFile not set
        if pArgs.outputFile == None:
            if pArgs.inputFile.endswith('.a'):
                # Strip off .a suffix
                pArgs.outputFile = pArgs.inputFile[:-2]
                pArgs.outputFile += '.' + bitCodeArchiveExtension

        logging.info('Writing output to {0}'.format(pArgs.outputFile))

        return archiveFiles(pArgs, bitCodeFiles)


class ExtractedArgs:

    fileType = None

    extractor = None

    arCmd = None


def extract_bc_args(args):

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
    parser.add_argument('--linker','-l',
                        dest='llvmLinker',
                        help='The LLVM bitcode linker to use. Default "%(default)s"',
                        default=llvmLinker)
    parser.add_argument('--archiver','-a',
                        dest='llvmArchiver',
                        help='The LLVM bitcode archiver to use. Default "%(default)s"',
                        default=llvmArchiver)
    parser.add_argument('--verbose','-v',
                        dest='verboseFlag',
                        help='Call the external procedures in verbose mode.',
                        action="store_true")
    parser.add_argument('--manifest', '-m',
                        dest='manifestFlag',
                        help='Write a manifest file listing all the .bc files used.',
                        action='store_true')
    parser.add_argument('--bitcode', '-b',
                        dest='bitcodeModuleFlag',
                        help='Extract a bitcode module rather than an archive. ' +
                        'Only useful when extracting from an archive.',
                        action='store_true')
    parser.add_argument('--output','-o',
                        dest='outputFile',
                        help='The output file. Defaults to a file in the same directory ' +
                             'as the input with the same name as the input but with an ' +
                             'added file extension (.'+ moduleExtension + ' for bitcode '+
                             'modules and .' + bitCodeArchiveExtension +' for bitcode archives)',
                        default=None)
    pArgs = parser.parse_args(namespace=ExtractedArgs())


    # Check file exists
    if not os.path.exists(pArgs.inputFile):
        logging.error('File "{0}" does not exist.'.format(pArgs.inputFile))
        return (False, None)

    pArgs.inputFile = os.path.abspath(pArgs.inputFile)


    # Check output destitionation if set
    outputFile = pArgs.outputFile
    if outputFile != None:
      # Get Absolute output path
      outputFile = os.path.abspath(outputFile)
      if not os.path.exists(os.path.dirname(outputFile)):
        logging.error('Output directory "{0}" does not exist.'.format(os.path.dirname(outputFile)))
        return (False, None)

    pArgs.output = outputFile

    return (True, pArgs)


def extraction(args):

    (success, pArgs) = extract_bc_args(args)

    if not success:
        return 1

    if ( sys.platform.startswith('freebsd') or  sys.platform.startswith('linux') ):

        process_file_unix(pArgs)

    elif sys.platform.startswith('darwin'):

        process_file_darwin(pArgs)

    else:
        #iam: do we work on anything else?
        logging.error('Unsupported or unrecognized platform: {0}'.format(sys.platform))
        return 1


def process_file_unix(pArgs):

    ft = FileType.getFileType(pArgs.inputFile)
    logging.debug('Detected file type is {0}'.format(FileType.revMap[ft]))

    pArgs.arCmd   =  ['ar', 'xv'] if pArgs.verboseFlag else ['ar', 'x']
    pArgs.extractor = extract_section_linux
    pArgs.fileType = FileType.ELF_OBJECT

    if ft == FileType.ELF_EXECUTABLE or ft == FileType.ELF_SHARED or ft == FileType.ELF_OBJECT:
        logging.info('Generating LLVM Bitcode module')
        return handleExecutable(pArgs)
    elif ft == FileType.ARCHIVE:
        if pArgs.bitcodeModuleFlag:
            logging.info('Generating LLVM Bitcode module from an archive')
        else:
            logging.info('Generating LLVM Bitcode archive from an archive')
        return handleArchive(pArgs)
    else:
        logging.error('File "{0}" of type {1} cannot be used'.format(pArgs.inputFile, FileType.revMap[ft]))
        return 1



def process_file_darwin(pArgs):

    ft = FileType.getFileType(pArgs.inputFile)
    logging.debug('Detected file type is {0}'.format(FileType.revMap[ft]))

    pArgs.arCmd   =  ['ar', '-x', '-v'] if pArgs.verboseFlag else ['ar', '-x']
    pArgs.extractor = extract_section_darwin
    pArgs.fileType =  FileType.MACH_OBJECT

    if ft == FileType.MACH_EXECUTABLE or ft == FileType.MACH_SHARED or ft == FileType.MACH_OBJECT:
        logging.info('Generating LLVM Bitcode module')
        return handleExecutable(pArgs)
    elif ft == FileType.ARCHIVE:
        if pArgs.bitcodeModuleFlag:
            logging.info('Generating LLVM Bitcode module from an archive')
        else:
            logging.info('Generating LLVM Bitcode archive from an archive')
        return handleArchive(pArgs)
    else:
        logging.error('File "{0}" of type {1} cannot be used'.format(pArgs.inputFile, FileType.revMap[ft]))
        return 1

