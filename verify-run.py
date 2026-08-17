from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

commands = [
    (["npm", "--prefix", "frontend", "run", "check"], ROOT),
    (["uv", "run", "--directory", "backend", "pytest", "-q"], ROOT),
    (["uv", "run", "--directory", "backend", "python", "-m", "compileall", "-q", "app", "tests"], ROOT),
]

for command, cwd in commands:
    result = subprocess.run(
        " ".join(command),
        cwd=cwd,
        shell=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)

# The verify runner expects the test command to terminate cleanly. Keep this
# script host-only; server startup is handled by the separate start command.
print("verification checks passed")
