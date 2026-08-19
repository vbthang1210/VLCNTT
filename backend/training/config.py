from __future__ import annotations

from pathlib import Path

SAMPLE_RATE = 16_000
CHANNELS = 1
AUDIO_DURATION = 1.0
NUM_SAMPLES = int(SAMPLE_RATE * AUDIO_DURATION)
N_FFT = 512
HOP_LENGTH = 160
N_MELS = 64
F_MIN = 20
F_MAX = 8_000
CLASS_NAMES = ["bat", "tat", "unknown", "silence"]
CLASS_TO_INDEX = {name: index for index, name in enumerate(CLASS_NAMES)}
NUM_CLASSES = len(CLASS_NAMES)
BATCH_SIZE = 32
NUM_EPOCHS = 30
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
NUM_WORKERS = 0
MODEL_VERSION = "keyword_cnn_v1"
CONFIDENCE_THRESHOLD = 0.80
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATASET_DIR = PROJECT_ROOT / "dataset" / "raw"
PROCESSED_DATASET_DIR = PROJECT_ROOT / "dataset" / "processed"
MODEL_PATH = PROJECT_ROOT / "backend" / "storage" / "models" / "keyword_cnn.pt"
MODEL_DIR = MODEL_PATH.parent
