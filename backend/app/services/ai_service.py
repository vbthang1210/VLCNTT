from dataclasses import dataclass
from pathlib import Path

import torch

from model.keyword_cnn import KeywordCNN

from training.config import (
    MODEL_PATH,
    CLASS_NAMES,
    NUM_CLASSES,
    CONFIDENCE_THRESHOLD,
)

from training.features import extract_features


@dataclass
class PredictionResult:

    label: str

    confidence: float

    accepted: bool

    model_version: str


class AIService:

    def __init__(
        self,
        model_path: Path = MODEL_PATH,
    ):

        self.device = torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "mps"
            if torch.backends.mps.is_available()
            else "cpu"
        )

        checkpoint = torch.load(
            model_path,
            map_location=self.device,
        )

        self.model = KeywordCNN(
            num_classes=NUM_CLASSES
        )

        self.model.load_state_dict(
            checkpoint["model_state_dict"]
        )

        self.model.to(self.device)

        self.model.eval()

        self.class_names = checkpoint[
            "class_names"
        ]

        self.model_version = checkpoint[
            "model_version"
        ]

    def predict(
        self,
        audio_path: str,
    ) -> PredictionResult:

        features = extract_features(
            audio_path
        )

        # [1, 64, T]
        # ↓
        # [1, 1, 64, T]

        features = features.unsqueeze(0)

        features = features.to(
            self.device
        )

        with torch.no_grad():

            logits = self.model(
                features
            )

            probabilities = torch.softmax(
                logits,
                dim=1,
            )

            confidence, class_index = (
                probabilities.max(dim=1)
            )

        confidence = confidence.item()

        class_index = class_index.item()

        label = self.class_names[
            class_index
        ]

        accepted = (
            confidence
            >= CONFIDENCE_THRESHOLD
        )

        return PredictionResult(
            label=label,
            confidence=confidence,
            accepted=accepted,
            model_version=self.model_version,
        )