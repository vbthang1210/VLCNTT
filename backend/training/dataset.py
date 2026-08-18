from pathlib import Path

import torch
from torch.utils.data import Dataset

from training.config import (
    CLASS_NAMES,
    CLASS_TO_INDEX,
)

from training.features import extract_features


AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".flac",
}


class KeywordDataset(Dataset):

    def __init__(self, root_dir):

        self.root_dir = Path(root_dir)

        self.samples = []

        for label in CLASS_NAMES:

            class_dir = self.root_dir / label

            if not class_dir.exists():
                continue

            for path in class_dir.rglob("*"):

                if path.suffix.lower() in AUDIO_EXTENSIONS:

                    self.samples.append(
                        (
                            path,
                            CLASS_TO_INDEX[label],
                        )
                    )

        if not self.samples:
            raise RuntimeError(
                f"No audio files found in {self.root_dir}"
            )

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):

        path, label = self.samples[index]

        features = extract_features(str(path))

        return features, torch.tensor(
            label,
            dtype=torch.long,
        )