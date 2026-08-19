from __future__ import annotations

import argparse
import hashlib
import random
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.config import PROCESSED_DATASET_DIR, RAW_DATASET_DIR

DEFAULT_RAW_DIR = RAW_DATASET_DIR
DEFAULT_OUTPUT_DIR = PROCESSED_DATASET_DIR

# Extension matching is case-insensitive. ffmpeg is used as a decoder fallback.
SUPPORTED_AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".alac",
    ".amr",
    ".caf",
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
    ".webm",
}


@dataclass(frozen=True)
class PreprocessSummary:
    originals: int
    augmentations: int
    failures: int


def _modules():
    try:
        import torch
        import torchaudio
    except ImportError as exc:
        raise RuntimeError("Install backend/requirements-ai.txt first") from exc
    return torch, torchaudio


def discover_audio_files(class_dir: Path) -> list[Path]:
    """Return supported audio files below one class directory recursively."""
    return sorted(
        path
        for path in class_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
    )


def output_stem_for(source: Path, class_dir: Path) -> str:
    """Build a readable, collision-safe name for a flattened class directory."""
    relative_path = source.relative_to(class_dir)
    readable = "__".join(relative_path.with_suffix("").parts)
    readable = re.sub(r"[^A-Za-z0-9_-]+", "_", readable).strip("_") or "audio"
    digest = hashlib.sha1(relative_path.as_posix().encode("utf-8")).hexdigest()[:8]
    return f"{readable}_{digest}"


def _load_with_ffmpeg(source: Path, torch):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError(
            f"Cannot decode {source.suffix or 'this format'}. Install ffmpeg "
            "(macOS: brew install ffmpeg) and run preprocessing again."
        )

    with tempfile.TemporaryDirectory(prefix="keyword_audio_") as temp_dir:
        decoded_path = Path(temp_dir) / "decoded.wav"
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-vn",
                "-acodec",
                "pcm_s16le",
                str(decoded_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not decoded_path.is_file():
            detail = result.stderr.strip() or "unknown ffmpeg error"
            raise RuntimeError(f"ffmpeg could not decode {source}: {detail}")
        # Do not call torchaudio.load() here. New torchaudio versions route even
        # ordinary WAV loading through TorchCodec, which defeats this fallback.
        with wave.open(str(decoded_path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            pcm_bytes = wav_file.readframes(frame_count)

        if channels <= 0 or sample_rate <= 0 or frame_count <= 0:
            raise RuntimeError(f"ffmpeg produced invalid audio for {source}")
        if sample_width != 2:
            raise RuntimeError(
                f"ffmpeg produced {sample_width * 8}-bit audio instead of PCM16"
            )

        # wave returns interleaved signed little-endian PCM16 samples.
        samples = torch.frombuffer(bytearray(pcm_bytes), dtype=torch.int16)
        waveform = samples.reshape(-1, channels).transpose(0, 1).float()
        waveform = waveform / 32768.0
        return waveform, sample_rate


def load_source_audio(source: Path, torch, torchaudio):
    """Use torchaudio first and fall back to ffmpeg for formats such as m4a."""
    try:
        return torchaudio.load(str(source))
    except Exception as torchaudio_error:
        try:
            return _load_with_ffmpeg(source, torch)
        except Exception as ffmpeg_error:
            raise RuntimeError(
                f"Unable to decode {source}. torchaudio: {torchaudio_error}; "
                f"ffmpeg: {ffmpeg_error}"
            ) from ffmpeg_error


def convert_to_model_format(waveform, source_rate: int, torchaudio):
    """Convert channels/sample rate without discarding long recordings."""
    from training.config import SAMPLE_RATE

    if waveform.ndim != 2 or waveform.shape[0] == 0 or waveform.shape[-1] == 0:
        raise ValueError("audio contains no samples")
    if source_rate <= 0:
        raise ValueError("audio has an invalid sample rate")

    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if source_rate != SAMPLE_RATE:
        waveform = torchaudio.functional.resample(waveform, source_rate, SAMPLE_RATE)

    return waveform


def split_into_model_windows(waveform, torch) -> list:
    """
    Split audio into consecutive one-second windows.

    Full 1-second windows are kept normally.

    The final partial window:
    - keep + pad if it contains at least 50% of a full window
    - discard if it is shorter than 50%

    This avoids producing samples such as:
        0.05s real audio + 0.95s silence
    with a keyword label.
    """
    from training.config import NUM_SAMPLES, SAMPLE_RATE

    MIN_WINDOW_RATIO = 0.5
    min_window_samples = int(NUM_SAMPLES * MIN_WINDOW_RATIO)

    windows = []
    total_samples = waveform.shape[-1]

    for start in range(0, total_samples, NUM_SAMPLES):

        window = waveform[..., start : start + NUM_SAMPLES]

        window_samples = window.shape[-1]

        # ----------------------------------------------------
        # Full window
        # ----------------------------------------------------

        if window_samples == NUM_SAMPLES:
            pass

        # ----------------------------------------------------
        # Partial window >= 0.5 second
        # Keep it and pad to exactly one second
        # ----------------------------------------------------

        elif window_samples >= min_window_samples:

            window = torch.nn.functional.pad(
                window,
                (
                    0,
                    NUM_SAMPLES - window_samples,
                ),
            )

        # ----------------------------------------------------
        # Partial window < 0.5 second
        # Discard it
        # ----------------------------------------------------

        else:

            print(
                "[SKIP SHORT WINDOW] "
                f"{window_samples} samples "
                f"({window_samples / SAMPLE_RATE:.3f}s)"
            )

            continue

        # ----------------------------------------------------
        # Peak normalization
        # ----------------------------------------------------

        peak = window.abs().max()

        if peak > 0:
            window = window / peak

        windows.append(
            window.clamp(
                -1.0,
                1.0,
            )
        )

    return windows


def augment_waveform(waveform, torch):
    """Apply random gain, zero-filled time shift and background noise."""
    from training.config import NUM_SAMPLES

    augmented = waveform.clone()
    augmented = augmented * random.uniform(0.75, 1.25)

    max_shift = max(1, int(NUM_SAMPLES * 0.12))
    shift = random.randint(-max_shift, max_shift)
    if shift > 0:
        augmented = torch.nn.functional.pad(augmented, (shift, 0))[..., :NUM_SAMPLES]
    elif shift < 0:
        augmented = torch.nn.functional.pad(augmented[..., -shift:], (0, -shift))

    noise_level = random.uniform(0.001, 0.02)
    augmented = augmented + torch.randn_like(augmented) * noise_level
    return augmented.clamp(-1.0, 1.0)


def _save_pcm16_wav(path: Path, waveform, torchaudio=None) -> None:
    from training.config import SAMPLE_RATE

    path.parent.mkdir(parents=True, exist_ok=True)
    if waveform.ndim != 2 or waveform.shape[0] == 0 or waveform.shape[-1] == 0:
        raise ValueError("cannot save an empty waveform")

    channels = int(waveform.shape[0])
    pcm16 = (
        waveform.detach()
        .cpu()
        .clamp(-1.0, 1.0)
        .transpose(0, 1)
        .contiguous()
        .mul(32767.0)
        .round()
        .short()
    )

    # Save with Python's standard wave module instead of torchaudio.save().
    # This avoids the TorchCodec requirement in recent torchaudio versions.
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm16.numpy().tobytes())


def process_dataset(
    raw_dir: Path,
    output_dir: Path,
    augmentations: int,
    seed: int,
) -> PreprocessSummary:
    torch, torchaudio = _modules()
    from training.config import CLASS_NAMES

    if augmentations < 0:
        raise ValueError("augmentations must be >= 0")

    random.seed(seed)
    torch.manual_seed(seed)
    raw_dir = Path(raw_dir)
    output_dir = Path(output_dir)
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"Raw dataset not found: {raw_dir}")

    originals_written = 0
    augmentations_written = 0
    failures: list[tuple[Path, Exception]] = []
    for class_name in CLASS_NAMES:
        class_dir = raw_dir / class_name
        if not class_dir.is_dir():
            raise FileNotFoundError(f"Missing class directory: {class_dir}")
        target_dir = output_dir / class_name

        for source in discover_audio_files(class_dir):
            try:
                waveform, source_rate = load_source_audio(source, torch, torchaudio)
                waveform = convert_to_model_format(
                    waveform,
                    source_rate,
                    torchaudio,
                )
                windows = split_into_model_windows(waveform, torch)
                stem = output_stem_for(source, class_dir)

                for part_index, window in enumerate(windows, start=1):
                    output = target_dir / f"{stem}_part{part_index:03d}.wav"
                    _save_pcm16_wav(output, window, torchaudio)
                    originals_written += 1

                    for augmentation_index in range(1, augmentations + 1):
                        augmented = augment_waveform(window, torch)
                        augmented_output = target_dir / (
                            f"{stem}_part{part_index:03d}"
                            f"_aug{augmentation_index:03d}.wav"
                        )
                        _save_pcm16_wav(
                            augmented_output,
                            augmented,
                            torchaudio,
                        )
                        augmentations_written += 1
            except Exception as exc:
                failures.append((source, exc))

    for source, error in failures:
        print(f"[FAILED] {source}: {error}", file=sys.stderr)

    summary = PreprocessSummary(
        originals=originals_written,
        augmentations=augmentations_written,
        failures=len(failures),
    )
    if failures:
        raise RuntimeError(
            f"Preprocessing completed with {len(failures)} failed file(s); "
            "see the messages above"
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recursively convert raw class folders to 1-second, 16 kHz, "
            "mono PCM16 WAV files."
        )
    )
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--augmentations",
        type=int,
        default=10,
        help="number of augmented files generated from each one-second window",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.augmentations < 0:
        parser.error("--augmentations must be >= 0")

    try:
        summary = process_dataset(
            args.raw,
            args.output,
            args.augmentations,
            args.seed,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")

    print(f"Processed dataset: {args.output}")
    print(f"Original files: {summary.originals}")
    print(f"Augmented files: {summary.augmentations}")


if __name__ == "__main__":
    main()