"""Simple result logging."""
import datetime


def log_result(host, result):
    timestamp = datetime.datetime.now().isoformat()
    print(f"[{timestamp}] ping result for {host}:\n{result}")
