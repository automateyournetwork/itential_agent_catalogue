"""Tiny network diagnostics CLI - ping a host and report the result."""
import sys

from diagnostics.network import ping_host
from diagnostics.logger import log_result


def main():
    if len(sys.argv) < 2:
        print("usage: cli.py <hostname>")
        sys.exit(1)
    host = sys.argv[1]
    result = ping_host(host)
    log_result(host, result)


if __name__ == "__main__":
    main()
