"""
  This module is intended to be imported by command line tools so they can
  configure the root logger so that other loggers used in other modules can
  inherit the configuration.
"""
import logging
import os
import sys

_loggingEnv = 'WLLVM_OUTPUT'
_validLogLevels = ['CRITICAL','ERROR', 'WARNING', 'INFO', 'DEBUG']
logging.basicConfig(level=logging.WARNING, format='%(levelname)s:%(message)s')
if os.getenv(_loggingEnv):
    level = os.getenv(_loggingEnv).upper()
    if not level in _validLogLevels:
        logging.error('"{0}" is not a valid value for {1} . Valid values are {2}'.format(
                      level, _loggingEnv, _validLogLevels))
        sys.exit(1)
    else:
        logging.getLogger().setLevel(getattr(logging, level))

# Adjust the format if debugging
if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
  formatter = logging.Formatter('%(levelname)s::%(module)s.%(funcName)s() at %(filename)s:%(lineno)d ::%(message)s')
  for h in logging.getLogger().handlers:
    h.setFormatter(formatter)

