#include <string>
#include <unistd.h>
#include <sys/resource.h>
#include <sys/wait.h>

void set_rlimit(int resource, rlim_t limit) {
	rlimit rlim{limit, limit};
	setrlimit(resource, &rlim);
}

int main(int argc, char *argv[]) {
	if (argc < 5) return 1;

	set_rlimit(RLIMIT_CPU, std::stoi(argv[1]));
	set_rlimit(RLIMIT_AS, std::atoi(argv[2]));
	set_rlimit(RLIMIT_FSIZE, std::atoi(argv[3]));
	
	execvp(argv[4], argv + 4);
}
