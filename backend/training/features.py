from __future__ import annotations

import wave
from pathlib import Path

import torch
import torchaudio

from training.config import (
    SAMPLE_RATE,
    NUM_SAMPLES,
)


# ============================================================
# Feature configuration
# ============================================================

N_MELS = 64

N_FFT = 512

HOP_LENGTH = 160

WIN_LENGTH = 400

EPSILON = 1e-6


# ============================================================
# WAV loading
# ============================================================

def load_audio(
    path: str | Path,
    target_sample_rate: int = SAMPLE_RATE,
    target_num_samples: int = NUM_SAMPLES,
) -> torch.Tensor:
    """
    Load a processed PCM16 WAV file without using torchaudio.load().

    Expected processed format:
        - WAV
        - PCM16
        - mono
        - 16 kHz
        - approximately 1 second

    Returns:
        Tensor with shape:
            [1, target_num_samples]

    This intentionally uses Python's standard wave module because
    recent torchaudio versions route torchaudio.load() through
    TorchCodec.
    """

    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Audio file not found: {path}"
        )

    # --------------------------------------------------------
    # Read PCM WAV using Python standard library
    # --------------------------------------------------------

    try:
        with wave.open(str(path), "rb") as wav_file:

            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            source_sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()

            pcm_bytes = wav_file.readframes(
                frame_count
            )

    except wave.Error as exc:
        raise RuntimeError(
            f"Invalid WAV file: {path}: {exc}"
        ) from exc

    # --------------------------------------------------------
    # Validate WAV
    # --------------------------------------------------------

    if channels <= 0:
        raise ValueError(
            f"Invalid channel count in {path}: "
            f"{channels}"
        )

    if source_sample_rate <= 0:
        raise ValueError(
            f"Invalid sample rate in {path}: "
            f"{source_sample_rate}"
        )

    if frame_count <= 0:
        raise ValueError(
            f"Audio file contains no frames: "
            f"{path}"
        )

    # PCM16 = 2 bytes / sample
    if sample_width != 2:
        raise ValueError(
            f"Expected PCM16 WAV but found "
            f"{sample_width * 8}-bit audio: "
            f"{path}"
        )

    # --------------------------------------------------------
    # PCM16 bytes -> torch Tensor
    # --------------------------------------------------------

    samples = torch.frombuffer(
        bytearray(pcm_bytes),
        dtype=torch.int16,
    )

    expected_values = (
        frame_count
        * channels
    )

    if samples.numel() != expected_values:
        raise ValueError(
            f"Unexpected PCM sample count in {path}. "
            f"Expected {expected_values}, "
            f"got {samples.numel()}."
        )

    # WAV PCM is interleaved:
    #
    # L R L R L R ...
    #
    # reshape:
    #
    # [frames, channels]
    #
    # then transpose:
    #
    # [channels, frames]
    waveform = samples.reshape(
        -1,
        channels,
    ).transpose(
        0,
        1,
    )

    waveform = waveform.float()

    # int16:
    #
    # -32768 ... +32767
    #
    # ->
    #
    # approximately -1 ... +1
    waveform = (
        waveform
        / 32768.0
    )

    # --------------------------------------------------------
    # Multi-channel -> mono
    # --------------------------------------------------------

    if waveform.shape[0] > 1:

        waveform = waveform.mean(
            dim=0,
            keepdim=True,
        )

    # --------------------------------------------------------
    # Resample if necessary
    # --------------------------------------------------------

    if source_sample_rate != target_sample_rate:

        waveform = torchaudio.functional.resample(
            waveform,
            source_sample_rate,
            target_sample_rate,
        )

    # --------------------------------------------------------
    # Ensure exact model input length
    # --------------------------------------------------------

    current_samples = waveform.shape[-1]

    if current_samples > target_num_samples:

        waveform = waveform[
            ...,
            :target_num_samples
        ]

    elif current_samples < target_num_samples:

        padding = (
            target_num_samples
            - current_samples
        )

        waveform = torch.nn.functional.pad(
            waveform,
            (
                0,
                padding,
            ),
        )

    return waveform.clamp(
        -1.0,
        1.0,
    )


# ============================================================
# Mel spectrogram
# ============================================================

def create_mel_transform():
    """
    Build the MelSpectrogram transform used by the model.
    """

    return torchaudio.transforms.MelSpectrogram(
        sample_rate=SAMPLE_RATE,
        n_fft=N_FFT,
        win_length=WIN_LENGTH,
        hop_length=HOP_LENGTH,
        n_mels=N_MELS,
    )


# One reusable transform instead of rebuilding it for
# every training sample.
MEL_TRANSFORM = create_mel_transform()


# ============================================================
# Feature normalization
# ============================================================

def normalize_features(
    features: torch.Tensor,
) -> torch.Tensor:
    """
    Normalize one Mel spectrogram.

    Output approximately has:
        mean = 0
        std  = 1
    """

    mean = features.mean()

    std = features.std()

    features = (
        features
        - mean
    ) / (
        std
        + EPSILON
    )

    return features


# ============================================================
# Feature extraction
# ============================================================

def extract_features(
    path: str | Path,
) -> torch.Tensor:
    """
    Convert a one-second WAV file into a normalized
    log-Mel spectrogram.

    Pipeline:

        PCM16 WAV
            ↓
        waveform [1, 16000]
            ↓
        MelSpectrogram
            ↓
        log
            ↓
        normalization
            ↓
        Tensor [1, N_MELS, time]
    """

    waveform = load_audio(
        path=path,
        target_sample_rate=SAMPLE_RATE,
        target_num_samples=NUM_SAMPLES,
    )

    # --------------------------------------------------------
    # Mel spectrogram
    # --------------------------------------------------------

    mel = MEL_TRANSFORM(
        waveform
    )

    # --------------------------------------------------------
    # Log compression
    # --------------------------------------------------------

    mel = torch.log(
        mel
        + EPSILON
    )

    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    mel = normalize_features(
        mel
    )

    return mel.float()