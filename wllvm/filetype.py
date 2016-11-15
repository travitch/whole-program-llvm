import os 

from subprocess import *

from .popenwrapper import Popen

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
