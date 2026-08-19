from pathlib import Path
import random

from app.services.ai_service import AIService


# ============================================================
# Paths
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

DATASET_DIR = PROJECT_ROOT / "dataset" / "processed"


def get_random_audio() -> Path:
    """
    Randomly select one WAV file from the processed dataset.
    """

    audio_files = list(DATASET_DIR.rglob("*.wav"))

    if not audio_files:
        raise RuntimeError(
            f"No WAV files found in dataset: {DATASET_DIR}"
        )

    return random.choice(audio_files)


def main():

    print("=" * 60)
    print("AI INFERENCE TEST")
    print("=" * 60)

    # --------------------------------------------------------
    # Random audio
    # --------------------------------------------------------

    audio_path = get_random_audio()

    # Folder name = expected label
    expected_label = audio_path.parent.name

    print(f"Dataset       : {DATASET_DIR}")
    print(f"Audio         : {audio_path}")
    print(f"Expected      : {expected_label}")

    # --------------------------------------------------------
    # Load AI
    # --------------------------------------------------------

    print("\nLoading AI model...")

    ai = AIService()

    print(f"AI ready      : {ai.ready}")

    if not ai.ready:
        print("ERROR: AI model is not ready")
        return

    # --------------------------------------------------------
    # Inference
    # --------------------------------------------------------

    print("\nRunning inference...")

    result = ai.predict(audio_path)

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)

    print(f"Expected      : {expected_label}")
    print(f"Predicted     : {result.label}")
    print(f"Confidence    : {result.confidence:.4f}")
    print(f"Accepted      : {result.accepted}")
    print(f"Model version : {result.model_version}")

    # --------------------------------------------------------
    # Check
    # --------------------------------------------------------

    print()

    if result.label == expected_label:
        print("PASS: Prediction is correct")
    else:
        print("FAIL: Prediction is incorrect")


if __name__ == "__main__":
    main()