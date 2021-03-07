# Feeping Creaturism:
#
# this is the all important version number used by pip.
#
#
"""
Version History:

1.0.0    - 8/2/2016 initial birth as a pip package.

1.0.1    - 8/2/2016 the rst gets a make over, and doc strings
           became more pervasive.

1.0.2    - 8/4/2016 dragonegg issues. trying to include a polite 'as' wrapper
           (i.e. not a  console_script called as).

1.0.3    - 8/4/2016 travis build fixes.

1.0.4    - 8/4/2016 travis build fixes, and exception handling fixes.

1.0.5    - 8/4/2016 exit value was upsetting travis.

1.0.6    - 8/9/2016 exit codes preserved; important for configure scripts like musl libc.

1.0.7    - 8/9/2016 logical restructuring; smaller bites.

1.0.8    - 8/9/2016 test and doc subdirectories are no longer included.

1.0.9    - 8/25/2016  Python 3.0 import fixes (Will Dietz)

1.0.10   - 9/26/2016  Apple's otool just gets biggier and buggier.

1.0.11   - 9/27/2016  Improved Apple's otool fix.

1.0.12   - 10/27/2016 Common flag support.

1.0.13   - 11/05/2016  pylint spots a few mistakes.

1.0.14   - 11/10/2016  --coverage flag.

1.0.15   - 11/15/2016  pylintification complete.

1.0.16   - 11/16/2016  ooops musl points out I screwed up the exit codes AGAIN.

1.0.17   - 11/23/2016  delcypher  #16  over at travitch's place.

1.0.18   - 4/11/2017  tentative solution to the -emit-llvm "out of context" experience.

1.0.19   - 4/19/2017  fixed a '-o' issue in extract-bc and added the bitcode store feature.

1.1.0    - 4/21/2017  no new features on the horizon, no new bugs?

1.1.1    - 4/25/2017 bugs introduced by the new fetures have hopefully been eradicated.

1.1.2    - 4/26/2017 encoding issues with hashlib in the python 3 swarm.

1.1.3    - 5/20/2017 fortran support via flang (pull #60 over at travitch's place)

1.1.4    - 7/24/2017 improvements motivated by gllvm and logic.

1.1.5    - 3/14/2018 fixes suggested by Alexander Bakst

1.2.0    - 4/24/2018 fixes suggested by building the Linux kernel and trying to harmonize with gllvm.
           4/28/2018 can handle thin archives, can sort bitcode input to llvm-{ar, link} and manifest via the -s switch.
           5/1/2018 can handle archives correctly (deal with multiple files with the same name in the archive).

1.2.1    - 5/13/2018  -fsanitize=  now recognized as a compile AND link flag (mothers day edition)

1.2.2    - 6/1/2018 lots of minor fixes from building big projects (and their dependencies) like tor

1.2.3    - 4/15/2019 The tax day version. Almost a years worth of tweaks from building large things like the Linux kernel.

1.2.4    - 4/15/2019 The tax day version, II. Testing the twine upload.

1.2.5    - 4/17/2019 Fixing the pip package, hopefully.

1.2.6    - 6/18/2019 Various compiler cmd line options parsing tweaks.

1.2.7    - 3/23/2020 Added the LLVM_BITCODE_GENERATION_FLAGS  to allow LTO support.

1.2.8    - 3/23/2020 Added the LLVM_BITCODE_GENERATION_FLAGS  to allow LTO support. (pip uploading issues)

1.2.9    - 2/20/2021 Various fixes:
                        wllvm-sanity-checker prints correctly now we are python3
                        Eliminated "....".format(...) in favor of f'...{thingy}....' How many times did python try to get this right?
                        e.g. handle -Wl,--start-group ... -Wl,--end-group properly.
                        e.g. -W and -w don't trip the compile only flag.
1.3.0     - 3/6/2021 otool seems to have changed its output format, so we need to tread more carefully.

"""

wllvm_version = '1.3.0'
wllvm_date = 'March 6 2021'
