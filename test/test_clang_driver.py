#!/usr/bin/env python

import os
from test_base_driver import root_directory, BaseDriverTest

__author__ = 'Benjamin Schubert, ben.c.schubert@gmail.com'



class ClangDriverTest(BaseDriverTest):
    """
    Clang driver tester
    """
    @property
    def env(self):
        """
        The different environment variables used by subprocess to compile with clang and wllvm
        :return:
        """
        env = os.environ.copy()
        env["CC"] = "wllvm"
        env["CXX"] = "wllvm++"
        env["LLVM_COMPILER"] = "clang"
        env["PATH"] = "{}:{}".format(root_directory, os.environ["PATH"])
        return env
