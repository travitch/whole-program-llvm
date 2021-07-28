// test1.cpp
#include "test1.h"
pthread_mutex_t m = PTHREAD_MUTEX_INITIALIZER;

int glb_ext = 1;

void lock() {
    pthread_mutex_lock(&m);
}

void unlock() {
    pthread_mutex_unlock(&m);
}

