import sys
import os
import subprocess as sp

explain_LLVM_COMPILER = """
The environment variable 'LLVM_COMPILER' is a switch. It should either
be set to 'clang' or 'dragonegg'. Anything else will cause an error.
"""

explain_LLVM_DRAGONEGG_PLUGIN = """
You need to set the environment variable LLVM_DRAGONEGG_PLUGIN to the full path
to your dragonegg plugin. Thanks.
"""

class Checker(object):
    def __init__(self):
        path = os.getenv('LLVM_COMPILER_PATH')
 
        if path and path[-1] != os.path.sep:
            path = path + os.path.sep

        self.path = path if path else ''

    def check(self):
        if not self.checkOS():
            print 'I do not think we support your OS. Sorry.'
            return 1

        success = self.checkCompiler()

        if success:
            self.checkAuxiliaries()
    
        return 0 if success else 1

        

    def checkOS(self):
        return (sys.platform.startswith('freebsd') or
                sys.platform.startswith('linux') or 
                sys.platform.startswith('darwin'))
    
            
    def checkSwitch(self):
        compiler_type = os.getenv('LLVM_COMPILER')
        if compiler_type == 'clang':
            return (1, 'Good, we are using clang.\n')
        elif compiler_type == 'dragonegg':
            return (2, 'OK, we are using dragonegg.\n')
        else:
            return (0, explain_LLVM_COMPILER)


    def checkClang(self):

        cc_name = os.getenv('LLVM_CC_NAME')
        cxx_name = os.getenv('LLVM_CXX_NAME')

        cc =  '{0}{1}'.format(self.path, cc_name if cc_name else 'clang')
        cxx = '{0}{1}'.format(self.path, cxx_name if cxx_name else 'clang++')

        return self.checkCompilers(cc, cxx)

    
    def checkDragonegg(self):

        if not self.checkDragoneggPlugin():
            return False

        pfx = ''
        if os.getenv('LLVM_GCC_PREFIX') is not None:
            pfx = os.getenv('LLVM_GCC_PREFIX')

        cc  = '{0}{1}gcc'.format(self.path, pfx)
        cxx = '{0}{1}g++'.format(self.path, pfx)

        (ccOk, ccVersion) = self.checkExecutable(cc)
        (cxxOk, cxxVersion) = self.checkExecutable(cxx)

        return self.checkCompilers(cc, cxx)

    
    def checkDragoneggPlugin(self):
        plugin = os.getenv('LLVM_DRAGONEGG_PLUGIN')

        if not plugin:
            print explain_LLVM_DRAGONEGG_PLUGIN
            return False

        if os.path.isfile(plugin):
            try: 
                open(plugin)
                pass
            except IOError as e:
                print "Unable to open {0}".format(plugin)
            else:
                return True
        else:
            print "Could not find {0}".format(plugin)
            return False
        

    def checkCompiler(self):
        (code, comment) = self.checkSwitch()

        if code == 0:
            print comment
            return False
        elif code == 1:
            print comment
            return self.checkClang()
        elif code == 2:
            print comment
            return self.checkDragonegg()
        else:
            print 'Insane\n'
            return False


    def checkCompilers(self, cc, cxx):

        (ccOk, ccVersion) = self.checkExecutable(cc)
        (cxxOk, cxxVersion) = self.checkExecutable(cxx)

        if not ccOk:
            print 'The C compiler {0} was not found or not executable.\nBetter not try using wllvm!\n'.format(cc)
        else:
            print 'The C compiler {0} is:\n{1}\n'.format(cc, ccVersion)

        if not cxxOk:
            print 'The CXX compiler {0} was not found or not executable.\nBetter not try using wllvm++!\n'.format(cxx)
        else:
            print 'The C++ compiler {0} is:\n{1}\n'.format(cxx, cxxVersion)
        
        return ccOk or cxxOk
        

    def checkExecutable(self, exe, version_switch='-v'):
        cmd = [exe, version_switch]
        try:
            compiler = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
            output = compiler.communicate()
            compilerOutput = '{0}{1}'.format(output[0], output[1])
        except OSError as e:
            return (False, '{0} not found or not executable'.format(exe))
        else:
            return (True, compilerOutput)
        

    
    def checkAuxiliaries(self):
        link = '{0}llvm-link'.format(self.path) if self.path else 'llvm-link'  #LLVM_LINKER_NAME
        ar = '{0}llvm-ar'.format(self.path) if self.path else 'llvm-ar'        #LLVM_ARCHIVER_NAME

        (linkOk, linkVersion) = self.checkExecutable(link, '-version') 

        (arOk, arVersion) =  self.checkExecutable(ar, '-version') 

        if not linkOk:
            print 'The bitcode linker {0} was not found or not executable.\nBetter not try using extract-bc!\n'.format(link)
        else:
            print 'The bitcode linker {0} is:\n{1}\n'.format(link, linkVersion)

        if not arOk:
            print 'The bitcode archiver {0} was not found or not executable.\nBetter not try using extract-bc!\n'.format(ar)
        else:
            print 'The bitcode archiver {0} is:\n{1}\n'.format(ar, arVersion)

        
