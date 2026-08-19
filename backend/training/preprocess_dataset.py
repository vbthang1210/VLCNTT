from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.config import PROCESSED_DATASET_DIR, RAW_DATASET_DIR

DEFAULT_RAW_DIR = RAW_DATASET_DIR
DEFAULT_OUTPUT_DIR = PROCESSED_DATASET_DIR


def _modules():
    try:
        import torch
        import torchaudio
    except ImportError as exc:
        raise RuntimeError("Install backend/requirements-ai.txt first") from exc
    return torch, torchaudio


def process_dataset(raw_dir: Path, output_dir: Path, augmentations: int, seed: int) -> None:
    torch, torchaudio = _modules()
    from training.config import CLASS_NAMES, NUM_SAMPLES, SAMPLE_RATE

    random.seed(seed)
    torch.manual_seed(seed)
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw dataset not found: {raw_dir}")
    for class_name in CLASS_NAMES:
        source_dir = raw_dir / class_name
        if not source_dir.exists():
            raise FileNotFoundError(f"Missing class directory: {source_dir}")
        target_dir = output_dir / class_name
        target_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(source_dir.rglob("*.wav")):
            waveform, rate = torchaudio.load(str(source))
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            if rate != SAMPLE_RATE:
                waveform = torchaudio.functional.resample(waveform, rate, SAMPLE_RATE)
            if waveform.shape[-1] > NUM_SAMPLES:
                waveform = waveform[..., :NUM_SAMPLES]
            elif waveform.shape[-1] < NUM_SAMPLES:
                waveform = torch.nn.functional.pad(
                    waveform,
                    (0, NUM_SAMPLES - waveform.shape[-1]),
                )
            peak = waveform.abs().max()
            if peak > 0:
                waveform = waveform / peak
            torchaudio.save(
                str(target_dir / source.name),
                waveform,
                SAMPLE_RATE,
                encoding="PCM_S",
                bits_per_sample=16,
            )
            for index in range(augmentations):
                augmented = waveform + (
                    torch.randn_like(waveform) * random.uniform(0.002, 0.015)
                )
                augmented = augmented.clamp(-1.0, 1.0)
                output = target_dir / f"{source.stem}_aug{index + 1:02d}.wav"
                torchaudio.save(
                    str(output),
                    augmented,
                    SAMPLE_RATE,
                    encoding="PCM_S",
                    bits_per_sample=16,
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--augmentations", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.augmentations < 0:
        parser.error("--augmentations must be >= 0")
    process_dataset(args.raw, args.output, args.augmentations, args.seed)
    print(f"Processed dataset: {args.output}")


if __name__ == "__main__":
    main()
