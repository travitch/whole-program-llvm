"""
  This module is intended to be imported by command line tools so they can
  configure the root logger so that other loggers used in other modules can
  inherit the configuration.
"""
import logging
import os
import sys

# iam: 6/30/2017 decided to move to a gllvm style where we can set the level and the output file
_loggingEnvLevel_old = 'WLLVM_OUTPUT'
_loggingEnvLevel_new = 'WLLVM_OUTPUT_LEVEL'

_loggingDestination = 'WLLVM_OUTPUT_FILE'

_validLogLevels = ['ERROR', 'WARNING', 'INFO', 'DEBUG']

def logConfig(name):

    destination = os.getenv(_loggingDestination)

    if destination:
        logging.basicConfig(filename=destination, level=logging.WARNING, format='%(levelname)s:%(message)s')
    else:
        logging.basicConfig(level=logging.WARNING, format='%(levelname)s:%(message)s')

    retval = logging.getLogger(name)

    # ignore old setting
    level = os.getenv(_loggingEnvLevel_new)

    if level:
        level = level.upper()
        if not level in _validLogLevels:
            logging.error('"%s" is not a valid value for %s or %s. Valid values are %s',
                          level, _loggingEnvLevel_old, _loggingEnvLevel_new, _validLogLevels)
            sys.exit(1)
        else:
            retval.setLevel(getattr(logging, level))

    # Adjust the format if debugging
    if retval.getEffectiveLevel() == logging.DEBUG:
        formatter = logging.Formatter('%(levelname)s::%(module)s.%(funcName)s() at %(filename)s:%(lineno)d ::%(message)s')
        for h in logging.getLogger().handlers:
            h.setFormatter(formatter)

    return retval

def loggingConfiguration():
    destination = os.getenv(_loggingDestination)
    level = os.getenv(_loggingEnvLevel_new)
    return (destination, level)


def informUser(msg):
    sys.stderr.write(msg)
