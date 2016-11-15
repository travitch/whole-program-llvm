"""
  This module is intended to be imported by command line tools so they can
  configure the root logger so that other loggers used in other modules can
  inherit the configuration.
"""
import logging
import os
import sys

_loggingEnv = 'WLLVM_OUTPUT'

_validLogLevels = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']

def logConfig(name):

    logging.basicConfig(level=logging.WARNING, format='%(levelname)s:%(message)s')

    retval = logging.getLogger(name)

    level = os.getenv(_loggingEnv)

    if level:
        level = level.upper()
        if not level in _validLogLevels:
            logging.error('"%s" is not a valid value for %s. Valid values are %s',
                          level, _loggingEnv, _validLogLevels)
            sys.exit(1)
        else:
            retval.setLevel(getattr(logging, level))

    # Adjust the format if debugging
    if retval.getEffectiveLevel() == logging.DEBUG:
        formatter = logging.Formatter('%(levelname)s::%(module)s.%(funcName)s() at %(filename)s:%(lineno)d ::%(message)s')
        for h in logging.getLogger().handlers:
            h.setFormatter(formatter)

    return retval
