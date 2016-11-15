import os
import subprocess
import pprint
import logging

# This module provides a wrapper for subprocess.POpen
# that can be used for debugging

# Internal logger
_logger = logging.getLogger(__name__)

def Popen(*pargs, **kwargs):
    _logger.debug("WLLVM Executing:\n" + pprint.pformat(pargs[0]) + "\nin: " +  os.getcwd())
    try:
        return subprocess.Popen(*pargs, **kwargs)
    except OSError:
        _logger.error("WLLVM Failed to execute: %s", pprint.pformat(pargs[0]))
        raise
