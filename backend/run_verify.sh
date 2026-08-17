#!/usr/bin/env bash
set -euo pipefail
uv run pytest -q
python -m compileall -q app tests
uv run python run.py
