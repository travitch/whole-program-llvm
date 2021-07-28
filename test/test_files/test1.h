// test1.h
#ifndef TEST1_H_
#define TEST1_H_
#include <pthread.h>
#include <stdio.h>

extern int glb_ext;
extern pthread_mutex_t m;

void lock();
void unlock();

#endif

