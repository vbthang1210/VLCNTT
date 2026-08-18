"""
Dataset preprocessing + augmentation for VLCNTT keyword spotting.

Input:
    dataset/raw/
        bat/
        tat/
        unknown/
        silence/

Output:
    dataset/processed/
        bat/
        tat/
        unknown/
        silence/

Audio contract:
    - WAV
    - mono
    - 16 kHz
    - PCM16
    - exactly 1.0 second

The raw dataset is NEVER modified.

Usage from repository root:
    python backend/training/preprocess_dataset.py

Optional:
    python backend/training/preprocess_dataset.py --augmentations 2
    python backend/training/preprocess_dataset.py --seed 42
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import torch
import torchaudio


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "dataset" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "dataset" / "processed"

CLASSES = ("bat", "tat", "unknown", "silence")

# These values match the current AI implementation plan/configuration.
SAMPLE_RATE = 16_000
DURATION_SECONDS = 1.0
NUM_SAMPLES = int(SAMPLE_RATE * DURATION_SECONDS)

# Augmentation defaults.
DEFAULT_AUGMENTATIONS = 2

# Keep augmentation probabilities explicit and reproducible.
NOISE_PROBABILITY = 0.50
GAIN_PROBABILITY = 0.50
SHIFT_PROBABILITY = 0.50

# Noise amplitude is intentionally small.
NOISE_MIN_STD = 0.002
NOISE_MAX_STD = 0.015

# Random gain in linear amplitude.
GAIN_MIN = 0.75
GAIN_MAX = 1.25

# Maximum time shift in samples.
MAX_SHIFT_SECONDS = 0.10


# ---------------------------------------------------------------------------
# Audio loading / normalization
# ---------------------------------------------------------------------------

def load_audio(path: Path) -> torch.Tensor:
    """
    Load audio and convert it to:
        [1, NUM_SAMPLES]
        mono
        16 kHz
        float32
        peak-normalized
    """
    waveform, sample_rate = torchaudio.load(str(path))

    # Convert multi-channel audio to mono.
    if waveform.ndim != 2:
        raise ValueError(f"Unexpected waveform shape {waveform.shape}: {path}")

    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    # Resample if necessary.
    if sample_rate != SAMPLE_RATE:
        waveform = torchaudio.functional.resample(
            waveform,
            orig_freq=sample_rate,
            new_freq=SAMPLE_RATE,
        )

    waveform = waveform.to(torch.float32)

    # Crop or zero-pad to exactly 1 second.
    waveform = crop_or_pad(waveform, NUM_SAMPLES)

    # Peak normalization.
    peak = waveform.abs().max()
    if peak > 0:
        waveform = waveform / peak

    return waveform


def crop_or_pad(waveform: torch.Tensor, target_samples: int) -> torch.Tensor:
    """Return waveform with exactly target_samples."""
    current = waveform.shape[-1]

    if current > target_samples:
        # Random crop is better for augmentation than always taking sample 0.
        max_start = current - target_samples
        start = random.randint(0, max_start)
        waveform = waveform[..., start : start + target_samples]

    elif current < target_samples:
        pad = target_samples - current
        waveform = torch.nn.functional.pad(waveform, (0, pad))

    return waveform


# ---------------------------------------------------------------------------
# Augmentations
# ---------------------------------------------------------------------------

def add_noise(waveform: torch.Tensor) -> torch.Tensor:
    """Add low-level Gaussian background noise."""
    std = random.uniform(NOISE_MIN_STD, NOISE_MAX_STD)
    noise = torch.randn_like(waveform) * std
    return waveform + noise


def random_gain(waveform: torch.Tensor) -> torch.Tensor:
    """Randomly change recording loudness."""
    gain = random.uniform(GAIN_MIN, GAIN_MAX)
    return waveform * gain


def random_time_shift(waveform: torch.Tensor) -> torch.Tensor:
    """
    Circularly shift the waveform by a small amount.

    This simulates the keyword appearing slightly earlier/later
    inside the 1-second window.
    """
    max_shift = int(SAMPLE_RATE * MAX_SHIFT_SECONDS)

    if max_shift <= 0:
        return waveform

    shift = random.randint(-max_shift, max_shift)

    if shift == 0:
        return waveform

    return torch.roll(waveform, shifts=shift, dims=-1)


def peak_normalize(waveform: torch.Tensor) -> torch.Tensor:
    """Normalize waveform peak to <= 1."""
    peak = waveform.abs().max()

    if peak > 0:
        waveform = waveform / peak

    return waveform.clamp(-1.0, 1.0)


def augment_waveform(waveform: torch.Tensor, class_name: str) -> torch.Tensor:
    """
    Apply a conservative random augmentation pipeline.

    For all classes:
        - gain
        - small time shift
        - low-level noise

    Silence is deliberately kept conservative: we do not create
    speech-like transformations for it.
    """
    augmented = waveform.clone()

    if random.random() < GAIN_PROBABILITY:
        augmented = random_gain(augmented)

    if random.random() < SHIFT_PROBABILITY:
        augmented = random_time_shift(augmented)

    if random.random() < NOISE_PROBABILITY:
        augmented = add_noise(augmented)

    # Ensure the result remains valid PCM range.
    augmented = peak_normalize(augmented)

    return augmented


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

def save_wav(waveform: torch.Tensor, output_path: Path) -> None:
    """Save a float waveform as 16-bit PCM WAV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    waveform = waveform.clamp(-1.0, 1.0)

    # torchaudio.save with bits_per_sample=16 writes PCM16 WAV.
    torchaudio.save(
        str(output_path),
        waveform,
        SAMPLE_RATE,
        encoding="PCM_S",
        bits_per_sample=16,
    )


# ---------------------------------------------------------------------------
# Dataset processing
# ---------------------------------------------------------------------------

def process_dataset(num_augmentations: int, seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)

    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"Raw dataset not found: {RAW_DIR}\n"
            "Create dataset/raw/{bat,tat,unknown,silence} first."
        )

    for class_name in CLASSES:
        class_dir = RAW_DIR / class_name

        if not class_dir.exists():
            print(f"[WARNING] Missing class directory: {class_dir}")
            continue

        output_dir = PROCESSED_DIR / class_name
        output_dir.mkdir(parents=True, exist_ok=True)

        files = sorted(
            p
            for p in class_dir.rglob("*")
            if p.is_file() and p.suffix.lower() == ".wav"
        )

        print(f"\n[{class_name}] {len(files)} raw files")

        for index, audio_path in enumerate(files, start=1):
            try:
                waveform = load_audio(audio_path)

                # Keep the original preprocessed sample.
                output_name = audio_path.stem + ".wav"
                save_wav(waveform, output_dir / output_name)

                # Generate augmented copies.
                for aug_index in range(1, num_augmentations + 1):
                    augmented = augment_waveform(waveform, class_name)

                    aug_name = (
                        f"{audio_path.stem}_aug{aug_index:02d}.wav"
                    )

                    save_wav(
                        augmented,
                        output_dir / aug_name,
                    )

                print(
                    f"  [{index:4d}/{len(files):4d}] "
                    f"{audio_path.name}"
                )

            except Exception as exc:
                print(
                    f"[ERROR] Failed to process {audio_path}: {exc}"
                )

    print("\n========================================")
    print("Dataset preprocessing completed.")
    print(f"Input : {RAW_DIR}")
    print(f"Output: {PROCESSED_DIR}")
    print("========================================")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preprocess and augment VLCNTT audio dataset."
    )

    parser.add_argument(
        "--augmentations",
        type=int,
        default=DEFAULT_AUGMENTATIONS,
        help=(
            "Number of augmented copies generated per raw WAV. "
            f"Default: {DEFAULT_AUGMENTATIONS}"
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility. Default: 42",
    )

    args = parser.parse_args()

    if args.augmentations < 0:
        parser.error("--augmentations must be >= 0")

    return args


def main() -> None:
    args = parse_args()
    process_dataset(
        num_augmentations=args.augmentations,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()