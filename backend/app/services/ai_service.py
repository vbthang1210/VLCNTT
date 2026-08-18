from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import torch

from model.keyword_cnn import KeywordCNN
from training.config import (
    CLASS_NAMES,
    CONFIDENCE_THRESHOLD,
    MODEL_PATH,
    NUM_CLASSES,
)
from training.features import extract_features

logger = logging.getLogger(__name__)


class AIUnavailable(RuntimeError):
    """Raised when inference is requested while the AI model is unavailable."""


@dataclass(frozen=True)
class PredictionResult:
    label: str
    confidence: float
    accepted: bool
    model_version: str


class AIService:
    """Load the keyword model once and provide safe inference for the backend."""

    def __init__(self, model_path: Path = MODEL_PATH):
        self.model_path = Path(model_path)
        self.device = self._select_device()

        self.model: KeywordCNN | None = None
        self.class_names = list(CLASS_NAMES)
        self.model_version: str | None = None
        self.error_code: str | None = None
        self.load_error: str | None = None

        self._load_model()

    @staticmethod
    def _select_device() -> torch.device:
        if torch.cuda.is_available():
            return torch.device("cuda")

        mps_backend = getattr(torch.backends, "mps", None)
        if mps_backend is not None and mps_backend.is_available():
            return torch.device("mps")

        return torch.device("cpu")

    @property
    def ready(self) -> bool:
        return self.model is not None and self.load_error is None

    def status(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "device": str(self.device),
            "model_version": self.model_version,
            "error_code": self.error_code,
            "error": self.load_error,
        }

    def _set_unavailable(self, code: str, message: str) -> None:
        self.model = None
        self.model_version = None
        self.error_code = code
        self.load_error = message
        logger.warning("[AI] %s | %s", code, message)

    def _load_model(self) -> None:
        if not self.model_path.is_file():
            self._set_unavailable(
                "AI_MODEL_NOT_FOUND",
                f"Keyword model not found: {self.model_path}",
            )
            return

        try:
            checkpoint = torch.load(
                self.model_path,
                map_location=self.device,
            )

            if not isinstance(checkpoint, dict):
                raise ValueError("checkpoint must be a dictionary")

            required_fields = {
                "model_state_dict",
                "class_names",
                "model_version",
            }
            missing_fields = required_fields.difference(checkpoint)
            if missing_fields:
                raise ValueError(
                    "checkpoint is missing fields: "
                    + ", ".join(sorted(missing_fields))
                )

            class_names = checkpoint["class_names"]
            if not isinstance(class_names, (list, tuple)):
                raise ValueError("checkpoint class_names must be a list")

            if len(class_names) != NUM_CLASSES:
                raise ValueError(
                    f"checkpoint has {len(class_names)} classes; "
                    f"expected {NUM_CLASSES}"
                )

            if list(class_names) != list(CLASS_NAMES):
                raise ValueError(
                    "checkpoint class_names do not match training config"
                )

            model = KeywordCNN(num_classes=NUM_CLASSES)
            model.load_state_dict(checkpoint["model_state_dict"])
            model.to(self.device)
            model.eval()

            self.model = model
            self.class_names = list(class_names)
            self.model_version = str(checkpoint["model_version"])
            self.error_code = None
            self.load_error = None

            logger.info(
                "[AI] Model ready | version=%s | device=%s | path=%s",
                self.model_version,
                self.device,
                self.model_path,
            )

        except Exception as exc:
            self._set_unavailable(
                "AI_MODEL_LOAD_FAILED",
                f"Unable to load keyword model: {exc}",
            )

    def predict(self, audio_path: str) -> PredictionResult:
        if not self.ready or self.model is None:
            raise AIUnavailable(
                self.load_error or "AI model is not ready"
            )

        path = Path(audio_path)
        if not path.is_file():
            raise ValueError(f"Audio file not found: {audio_path}")

        features = extract_features(str(path))

        # extract_features -> [1, n_mels, time]
        # CNN input       -> [batch, channel, n_mels, time]
        features = features.unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(features)
            probabilities = torch.softmax(logits, dim=1)
            confidence, class_index = probabilities.max(dim=1)

        confidence_value = float(confidence.item())
        class_index_value = int(class_index.item())
        label = self.class_names[class_index_value]

        return PredictionResult(
            label=label,
            confidence=confidence_value,
            accepted=confidence_value >= CONFIDENCE_THRESHOLD,
            model_version=self.model_version or "unknown",
        )
