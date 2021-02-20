""" A static class that allows the type of a file to be checked.
"""
import os

from subprocess import PIPE

from .popenwrapper import Popen

class FileType:
    """ A hack to grok the type of input files.
    """

    # These are just here to keep pylint happy.
    UNKNOWN = None
    ELF_EXECUTABLE = None
    ELF_OBJECT = None
    ELF_SHARED = None
    MACH_EXECUTABLE = None
    MACH_OBJECT = None
    MACH_SHARED = None
    ARCHIVE = None
    THIN_ARCHIVE = None


    # Provides int -> str map
    revMap = {}

    @classmethod
    def getFileType(cls, fileName):
        """ Returns the type of a file.

        This is a hacky way of determining
        the type of file we are looking at.
        Maybe we should use python-magic instead?
        """
        retval = None
        fileP = Popen(['file', os.path.realpath(fileName)], stdout=PIPE)
        output = fileP.communicate()[0]
        foutput = output.decode()
        foutput = foutput.split(' ', 1)[1] # Strip file path

        if 'ELF' in foutput and 'executable' in foutput:
            retval = cls.ELF_EXECUTABLE
        elif 'Mach-O' in foutput and 'executable' in foutput:
            retval = cls.MACH_EXECUTABLE
        elif 'ELF' in foutput and 'shared' in foutput:
            retval = cls.ELF_SHARED
        elif 'Mach-O' in foutput and 'dynamically linked shared' in foutput:
            retval = cls.MACH_SHARED
        elif 'current ar archive' in foutput:
            retval = cls.ARCHIVE
        elif 'thin archive' in foutput:
            retval = cls.THIN_ARCHIVE
        elif 'ELF' in foutput and 'relocatable' in foutput:
            retval = cls.ELF_OBJECT
        elif 'Mach-O' in foutput and 'object' in foutput:
            retval = cls.MACH_OBJECT
        else:
            retval = cls.UNKNOWN

        return retval


    @classmethod
    def getFileTypeString(cls, fti):
        """ Returns the string name of the file type.

        """
        if fti in cls.revMap:
            return cls.revMap[fti]
        return 'UNKNOWN'

    @classmethod
    def init(cls):
        """ Initializes the static fields.
        """
        for (index, name) in enumerate(('UNKNOWN',
                                        'ELF_EXECUTABLE',
                                        'ELF_OBJECT',
                                        'ELF_SHARED',
                                        'MACH_EXECUTABLE',
                                        'MACH_OBJECT',
                                        'MACH_SHARED',
                                        'ARCHIVE',
                                        'THIN_ARCHIVE')):
            setattr(cls, name, index)
            cls.revMap[index] = name

# Initialise FileType static class
FileType.init()
