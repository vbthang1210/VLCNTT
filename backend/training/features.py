from __future__ import annotations

from pathlib import Path


def _torch_modules():
    try:
        import torch
        import torchaudio
    except ImportError as exc:
        raise RuntimeError("Install backend/requirements-ai.txt to use AI features") from exc
    return torch, torchaudio


def load_audio(path: str, sample_rate: int = 16_000, num_samples: int = 16_000):
    torch, torchaudio = _torch_modules()
    waveform, source_rate = torchaudio.load(str(Path(path)))
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if source_rate != sample_rate:
        waveform = torchaudio.transforms.Resample(source_rate, sample_rate)(waveform)
    peak = waveform.abs().max()
    if peak > 0:
        waveform = waveform / peak
    if waveform.shape[-1] > num_samples:
        waveform = waveform[..., :num_samples]
    elif waveform.shape[-1] < num_samples:
        waveform = torch.nn.functional.pad(waveform, (0, num_samples - waveform.shape[-1]))
    return waveform


def extract_features(path: str):
    torch, torchaudio = _torch_modules()
    from .config import F_MAX, F_MIN, HOP_LENGTH, N_FFT, N_MELS, NUM_SAMPLES, SAMPLE_RATE

    waveform = load_audio(path, SAMPLE_RATE, NUM_SAMPLES)
    mel = torchaudio.transforms.MelSpectrogram(
        sample_rate=SAMPLE_RATE,
        n_fft=N_FFT,
        hop_length=HOP_LENGTH,
        n_mels=N_MELS,
        f_min=F_MIN,
        f_max=F_MAX,
    )(waveform)
    mel = torchaudio.transforms.AmplitudeToDB(stype="power")(mel)
    std = mel.std()
    if std > 0:
        mel = (mel - mel.mean()) / std
    return mel
