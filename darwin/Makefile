all:
	${CC} foo.c  -c
	${CC} bar.c  -c
	${CC} baz.c  -c
	${CC} main.c -c
	${CC} foo.o bar.o baz.o main.o -o main


clean:
	rm -f *.o main .*.o.bc .*.o *.bc .*.bc a.out *.s *.i

