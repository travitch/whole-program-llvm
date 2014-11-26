
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

