from __future__ import annotations

from pathlib import Path

from .config import CLASS_NAMES, CLASS_TO_INDEX
from .features import extract_features


class KeywordDataset:
    def __init__(self, root_dir):
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("Install backend/requirements-ai.txt to train the model") from exc
        self._torch = torch
        self.root_dir = Path(root_dir)
        self.samples = []
        for label in CLASS_NAMES:
            class_dir = self.root_dir / label
            if class_dir.exists():
                self.samples.extend(
                    (path, CLASS_TO_INDEX[label])
                    for path in class_dir.rglob("*")
                    if path.suffix.lower() in {".wav", ".mp3", ".flac"}
                )
        if not self.samples:
            raise RuntimeError(f"No audio files found in {self.root_dir}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        path, label = self.samples[index]
        return extract_features(str(path)), self._torch.tensor(label, dtype=self._torch.long)
