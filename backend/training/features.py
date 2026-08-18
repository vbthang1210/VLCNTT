import torch
import torchaudio

from training.config import (
    SAMPLE_RATE,
    NUM_SAMPLES,
    N_FFT,
    HOP_LENGTH,
    N_MELS,
    F_MIN,
    F_MAX,
)


_mel_transform = torchaudio.transforms.MelSpectrogram(
    sample_rate=SAMPLE_RATE,
    n_fft=N_FFT,
    hop_length=HOP_LENGTH,
    n_mels=N_MELS,
    f_min=F_MIN,
    f_max=F_MAX,
)

_amplitude_to_db = torchaudio.transforms.AmplitudeToDB(
    stype="power",
)


def load_audio(path: str) -> torch.Tensor:
    """
    Load audio and return:
        Tensor shape: [1, num_samples]
    """

    waveform, sample_rate = torchaudio.load(path)

    # Convert stereo -> mono
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    # Resample if necessary
    if sample_rate != SAMPLE_RATE:
        resampler = torchaudio.transforms.Resample(
            orig_freq=sample_rate,
            new_freq=SAMPLE_RATE,
        )

        waveform = resampler(waveform)

    # Normalize
    max_value = waveform.abs().max()

    if max_value > 0:
        waveform = waveform / max_value

    # Crop / pad
    waveform = fix_audio_length(waveform)

    return waveform


def fix_audio_length(waveform: torch.Tensor) -> torch.Tensor:
    """
    Force audio to exactly NUM_SAMPLES.
    """

    current_length = waveform.shape[-1]

    if current_length > NUM_SAMPLES:
        waveform = waveform[..., :NUM_SAMPLES]

    elif current_length < NUM_SAMPLES:
        padding = NUM_SAMPLES - current_length

        waveform = torch.nn.functional.pad(
            waveform,
            (0, padding),
        )

    return waveform


def audio_to_mel(waveform: torch.Tensor) -> torch.Tensor:
    """
    Convert waveform to log Mel Spectrogram.

    Input:
        [1, num_samples]

    Output:
        [1, n_mels, time]
    """

    mel = _mel_transform(waveform)

    mel = _amplitude_to_db(mel)

    # Per-sample normalization
    mean = mel.mean()
    std = mel.std()

    if std > 0:
        mel = (mel - mean) / std

    return mel


def extract_features(path: str) -> torch.Tensor:
    waveform = load_audio(path)

    mel = audio_to_mel(waveform)

    return mel