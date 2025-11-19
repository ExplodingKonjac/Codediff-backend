// AI generated test data generator
#include "testlib.h"
#include <iostream>
#include <random>
#include <vector>
using namespace std;

int main(int argc, char *argv[]) {
	registerGen(argc, argv, 1);

    random_device rd;
    mt19937 gen(rd());

    // Random test case type
    uniform_int_distribution<> type_dist(1, 3);
    int test_type = type_dist(gen);

    if (test_type == 1) {
        // Simple A+B
        uniform_int_distribution<> num_dist(1, 1000);
        int a = num_dist(gen);
        int b = num_dist(gen);
        cout << a << " " << b << endl;
    } else if (test_type == 2) {
        // Edge cases
        vector<int> edge_cases = {0, 1, -1, INT_MAX, INT_MIN};
        uniform_int_distribution<> idx_dist(0, edge_cases.size() - 1);
        int a = edge_cases[idx_dist(gen)];
        int b = edge_cases[idx_dist(gen)];
        cout << a << " " << b << endl;
    } else {
        // Random large numbers
        uniform_int_distribution<long long> large_dist(-1000000000, 1000000000);
        long long a = large_dist(gen);
        long long b = large_dist(gen);
        cout << a << " " << b << endl;
    }

    return 0;
}