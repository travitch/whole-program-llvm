#!/usr/bin/env python

import os
from test_base_driver import root_directory, BaseDriverTest

__author__ = 'Benjamin Schubert, ben.c.schubert@gmail.com'


class DragonEggDriverTest(BaseDriverTest):
    """
    Dragonegg driver tester
    """
    @property
    def env(self):
        """
        The different environment variables used by subprocess to compile with dragonegg and wllvm
        :return:
        """
        env = os.environ.copy()
        env["CC"] = "wllvm"
        env["CXX"] = "wllvm++"
        env["LLVM_COMPILER"] = "dragonegg"
        env["PATH"] = "{}:{}".format(root_directory, os.environ["PATH"])
        # FIXME find dragonegg path generically
        env["LLVM_DRAGONEGG_PLUGIN"] = "/usr/lib/gcc/x86_64-linux-gnu/4.7/plugin/dragonegg.so"
        env["LLVM_GCC_PREFIX"] = "llvm-"
        return env
