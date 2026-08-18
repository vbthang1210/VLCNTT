from pathlib import Path

# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASET_DIR = PROJECT_ROOT / "dataset"
RAW_DATASET_DIR = DATASET_DIR / "raw"

MODEL_DIR = PROJECT_ROOT / "backend" / "storage" / "models"

MODEL_PATH = MODEL_DIR / "keyword_cnn.pt"


# ============================================================
# LABELS
# ============================================================

CLASS_NAMES = [
    "bat",
    "tat",
    "unknown",
    "silence",
]

NUM_CLASSES = len(CLASS_NAMES)

CLASS_TO_INDEX = {
    name: index
    for index, name in enumerate(CLASS_NAMES)
}

INDEX_TO_CLASS = {
    index: name
    for index, name in enumerate(CLASS_NAMES)
}


# ============================================================
# AUDIO
# ============================================================

SAMPLE_RATE = 16000

CHANNELS = 1

AUDIO_DURATION = 1.0

NUM_SAMPLES = int(SAMPLE_RATE * AUDIO_DURATION)


# ============================================================
# MEL SPECTROGRAM
# ============================================================

N_FFT = 512

HOP_LENGTH = 160

N_MELS = 64

F_MIN = 20

F_MAX = 8000


# ============================================================
# TRAINING
# ============================================================

BATCH_SIZE = 32

NUM_EPOCHS = 30

LEARNING_RATE = 1e-3

WEIGHT_DECAY = 1e-4

NUM_WORKERS = 0


# ============================================================
# MODEL
# ============================================================

MODEL_VERSION = "keyword_cnn_v1"


# ============================================================
# INFERENCE
# ============================================================

CONFIDENCE_THRESHOLD = 0.80