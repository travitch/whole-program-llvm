// test2.cpp
#include "test1.h"

using namespace std;

int glb_test;

void *Thread1(void* x) {
    lock();
    glb_test++;
    unlock();
    return nullptr;
}

void *Thread2(void* x) {
    lock();
    glb_test++;
    unlock();
    return nullptr;
}

int main() {
    pthread_t t[2];
    pthread_create(&t[0], nullptr, Thread1, nullptr);
    pthread_create(&t[1], nullptr, Thread1, nullptr);
    pthread_join(t[0], nullptr);
    pthread_join(t[1], nullptr);
    return 0;
}
