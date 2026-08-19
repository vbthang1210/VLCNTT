from pathlib import Path
import subprocess
import sys


def test_backend_package_imports_from_repository_root():
    project_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend.app.services.ai_service import AIService; print(AIService.__name__)",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "AIService"