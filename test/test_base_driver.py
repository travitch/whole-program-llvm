#!/usr/bin/env python

__author__ = 'Benjamin Schubert, ben.c.schubert@gmail.com'

from abc import abstractproperty
import os
import shutil
import subprocess
import unittest


test_output_directory = "/tmp/test-wllvm"
test_files_directory = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_files")
root_directory = os.path.join(os.path.dirname(os.path.dirname(__file__)))


class BaseDriverTest(unittest.TestCase):
    """
    This is a BaseDriverTest class. Can be used to generically test that every driver works correctly with different
    code examples without any problem. This class is meant to be overridden
    """
    @classmethod
    def setUpClass(cls):
        """
        This is a base class that should not be run in tests, skip it
        :return:
        """
        if cls is BaseDriverTest:
            raise unittest.SkipTest("Skip BaseDriverTest, it's a base class")

    @abstractproperty
    def env(self):
        """
        Defines all necessary environment variables to allow the driver to be tested, assembly seen in "Usage" in the README
        """
        return None

    def setUp(self):
        """
        Creates the test directory in /tmp
        :return:
        """
        if not os.path.exists(test_output_directory):
            os.makedirs(test_output_directory)

    def tearDown(self):
        """
        remove all temporary test files
        :return:
        """
        shutil.rmtree(test_output_directory)

    def launch_proc(self, cmd):
        """
        Launches cmd with environment and in test_output_directory
        :param cmd: command to launch
        :return: the subprocess instance
        """
        return subprocess.Popen(cmd, shell=True, env=self.env, cwd=test_output_directory)

    def create_objects(self):
        """
        Creates some objects used by tests
        :return:
        """
        for f in ["foo.c", "bar.c", "baz.c", "main.c"]:
            self.assertEqual(self.launch_proc("${{CC}} {dir}/{f} -c".format(dir=test_files_directory, f=f)).wait(), 0)

    def create_archive(self):
        """
        creates the libfoo.a archive
        :return:
        """
        proc1 = self.launch_proc("ar cr libfoo.a foo.o bar.o baz.o")
        self.assertEqual(proc1.wait(), 0)

    def test_can_compile_simple_file(self):
        """
        Checks that it is possible to compile a single simple file
        :return:
        """
        proc = self.launch_proc("${{CXX}} -o hello {}/hello.cc".format(test_files_directory))
        self.assertEqual(proc.wait(), 0)

    def test_can_compile_multiple_file_in_one_object(self):
        """
        Checks that is is possible to compile multiple files into one executable
        :return:
        """
        proc = self.launch_proc(
            "${{CC}} {dir}/foo.c {dir}/bar.c {dir}/baz.c {dir}/main.c -o main".format(dir=test_files_directory)
        )
        self.assertEqual(proc.wait(), 0)

    def test_can_compile_and_link_multiple_object(self):
        """
        Checks that is is possible to compile first then link the compiled objects together
        :return:
        """
        proc1 = self.launch_proc(
            "${{CC}} {dir}/foo.c {dir}/bar.c {dir}/baz.c {dir}/main.c -c".format(dir=test_files_directory)
        )
        self.assertEqual(proc1.wait(), 0)

        proc2 = self.launch_proc("${CC} foo.o bar.o baz.o main.o -o main")
        self.assertEqual(proc2.wait(), 0)

    def test_can_compile_and_link_object_and_source_object(self):
        """
        Checks that is is possible to compile some objects first, then link them while compiling others
        :return:
        """
        proc1 = self.launch_proc("${{CC}} {dir}/foo.c {dir}/bar.c -c".format(dir=test_files_directory))
        self.assertEqual(proc1.wait(), 0)

        proc2 = self.launch_proc("${{CC}} foo.o bar.o {dir}/baz.c {dir}/main.c -o main".format(dir=test_files_directory))
        self.assertEqual(proc2.wait(), 0)

    def test_can_link_multiple_objects_together(self):
        """
        Checks that it is possible to link multiple objects together
        :return:
        """
        self.create_objects()
        proc = self.launch_proc("${CC} foo.o bar.o baz.o main.o -o main")
        self.assertEqual(proc.wait(), 0)

    def test_can_create_archive_from_object_created(self):
        """
        Checks that it is possible to create a valid archive from the created objects
        :return:
        """
        self.create_objects()
        self.create_archive()

        proc2 = self.launch_proc("ranlib libfoo.a")
        self.assertEqual(proc2.wait(), 0)

    def test_can_create_dynamic_library_from_objects(self):
        """
        Checks that is is possible to create a dynamic library from the objects
        :return:
        """
        self.create_objects()
        proc = self.launch_proc("${CC} -dynamiclib foo.o bar.o baz.o main.o -o libfoo.dylib")
        self.assertEqual(proc.wait(), 0)

    def test_can_deadstrip_dynamic_library(self):
        """
        Checks that is is possible to create a deadstripped dynamic library from the objects
        :return:
        """
        self.create_objects()
        proc = self.launch_proc("${CC} -dynamiclib -Wl,-dead_strip foo.o bar.o baz.o main.o -o libfoo.dylib")
        self.assertEqual(proc.wait(), 0)

    def test_can_link_with_archive(self):
        """
        Checks that is is possible to link with a created archive
        :return:
        """
        self.create_objects()
        self.create_archive()

        proc = self.launch_proc("${CC} main.o libfoo.a -o main.arch")
        self.assertEqual(proc.wait(), 0)


if __name__ == '__main__':
    unittest.main()
