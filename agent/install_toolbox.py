"""Download Google's pinned Toolbox release, verifying its published SHA256."""
import hashlib
import platform
import urllib.request
from pathlib import Path

VERSION = "v1.14.0"
TARGETS = {
    ("Linux", "x86_64"): ("linux/amd64", "8ff7c6034d792e2754999e101116ac63b8a9fb926dd2f736065d8e0ef85ead22"),
    ("Darwin", "arm64"): ("darwin/arm64", "d1578b3f551b1aa0947c7b377716cd5e8b9448ac5a79fdc1e06dc11a69bbe334"),
}
target, expected = TARGETS[(platform.system(), platform.machine())]
binary = Path("bin/toolbox")
binary.parent.mkdir(exist_ok=True)
if not binary.exists() or hashlib.sha256(binary.read_bytes()).hexdigest() != expected:
    data = urllib.request.urlopen(f"https://storage.googleapis.com/mcp-toolbox-for-databases/{VERSION}/{target}/toolbox", timeout=120).read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("Toolbox checksum mismatch")
    binary.write_bytes(data)
binary.chmod(0o755)
print(f"Verified {binary} {VERSION}")
