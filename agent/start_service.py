"""Supervise Toolbox and ADK; stop the container if either process fails."""
import os
import signal
import subprocess
import time
from pathlib import Path
from setup import render

render(Path("tools.yaml"))
children = []


def stop(*_):
    for child in children:
        if child.poll() is None:
            child.terminate()


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    children.append(subprocess.Popen(["bin/toolbox", "--config", "tools.yaml", "--address", "127.0.0.1", "--port", "5000", "--disable-version-check"]))
    children.append(subprocess.Popen(["python", "-m", "uvicorn", "service:app", "--host", "0.0.0.0", "--port", os.environ.get("PORT", "8080")]))
    while all(child.poll() is None for child in children):
        time.sleep(0.5)
finally:
    stop()
    for child in children:
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
raise SystemExit(1)
