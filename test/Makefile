# currently many works; neither one nor two, nor mix work
# one possibility is to do each .c file in turn
# essentially turning one and two into many. 
#
# two strategies:

# the important
# point is to make sure for each generated .*.bc file that
# there is a corresponding *.o file. so we may have to alter
# both "stages" of the compilation, or extend the second one substantially.

# just alter the second phase to get the many.
# Including the thing we are not supposed be able to do 
# which is attach the bit bitcode paths directly to the executable.
# in the mix version we will need to to append to a section. which
# has to be done by reading, removing then wrtiting the section.

zero:
	${CXX} hello.cc -o hello

one:
	${CC} foo.c bar.c baz.c main.c -o main

two:
	${CC} foo.c bar.c baz.c main.c -c
	${CC} foo.o bar.o baz.o main.o -o main

mix:
	${CC} foo.c bar.c -c
	${CC} foo.o bar.o baz.c main.c -o main

many:
	${CC} foo.c  -c
	${CC} bar.c  -c
	${CC} baz.c  -c
	${CC} main.c -c
	${CC} -Ioff/in/lala/land -I some/where/else foo.o bar.o baz.o main.o -lm -Lz -o main


clean:
	rm -f *.o main .*.o.bc .*.o *.bc .*.bc a.out *.s *.i hello

