#include <string>
#include <cstdint>
#include <unistd.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <sys/fcntl.h>

struct ChildData {
	int exit_status;
	std::uint64_t user_time_us;
	std::uint64_t system_time_us;
	std::uint64_t memory_kb;
};

void set_rlimit(int resource, rlim_t limit) {
	rlimit rlim{limit, limit};
	setrlimit(resource, &rlim);
}

int main(int argc, char *argv[]) {
	if (argc < 5) return 1;

	int rlim_cpu = std::stoi(argv[1]);
	int rlim_as = std::atoi(argv[2]);
	int rlim_fsz = std::atoi(argv[3]);
	int report_fd = std::atoi(argv[4]);

	if (fcntl(report_fd, F_SETFD, O_CLOEXEC) == -1) {
		std::perror("fcntl() failed");
		return 1;
	}

	int pid = fork();
	if (pid == -1) {
		std::perror("fork() failed");
		return 1;
	} else if (pid == 0) {
		if (execvp(argv[5], argv + 5) == -1) {
			std::perror("execvp() failed");
			return 1;
		}
	} else {
		rusage usage;
		int status;
		wait4(pid, &status, 0, &usage);

		ChildData res {
			.exit_status=status,
			.user_time_us=usage.ru_utime.tv_sec * 1000000 + usage.ru_utime.tv_usec,
			.system_time_us=usage.ru_stime.tv_sec * 1000000 + usage.ru_stime.tv_usec,
			.memory_kb=usage.ru_maxrss
		};
		if (write(report_fd, &res, sizeof(res)) != sizeof(res)) {
			perror("write() failed");
			return 1;
		}
		return 0;
	}
}
