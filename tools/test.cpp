#include <iostream>
#include <cstdint>
#include "testlib.h"

using namespace std;

int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);

    constexpr int64_t MIN_VAL = -(1LL << 31);
    constexpr int64_t MAX_VAL = (1LL << 31) - 1;

    int64_t a = rnd.next(MIN_VAL, MAX_VAL);
    int64_t b = rnd.next(MIN_VAL, MAX_VAL);

    // Ensure the sum does not overflow int64_t (it won't, since both are 32-bit ints)
    // But we still output as integers in valid range.

    cout << a << " " << b << endl;

    return 0;
}