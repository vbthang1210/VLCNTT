import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.config import MODEL_DIR, MODEL_PATH, PROCESSED_DATASET_DIR
from training.preprocess_dataset import DEFAULT_OUTPUT_DIR, DEFAULT_RAW_DIR
from training.train import DEFAULT_DATASET_DIR


def test_training_uses_preprocessed_dataset_by_default():
    assert DEFAULT_DATASET_DIR == PROCESSED_DATASET_DIR


def test_model_directory_matches_checkpoint_path():
    assert MODEL_DIR == MODEL_PATH.parent


def test_preprocessing_defaults_use_project_paths():
    from training.config import RAW_DATASET_DIR

    assert DEFAULT_RAW_DIR == RAW_DATASET_DIR
    assert DEFAULT_OUTPUT_DIR == PROCESSED_DATASET_DIR


def test_training_help_does_not_require_optional_torch():
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "training" / "train.py"),
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--dataset" in result.stdout