from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

try:
    from training.config import CLASS_NAMES, CONFIDENCE_THRESHOLD, MODEL_PATH, NUM_CLASSES
except ModuleNotFoundError:
    from backend.training.config import CLASS_NAMES, CONFIDENCE_THRESHOLD, MODEL_PATH, NUM_CLASSES

logger = logging.getLogger(__name__)


class AIUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionResult:
    label: str
    confidence: float
    accepted: bool
    model_version: str


class AIService:
    def __init__(self, model_path: Path = MODEL_PATH):
        self.model_path = Path(model_path)
        self.model = None
        self.device = "unavailable"
        self.class_names = list(CLASS_NAMES)
        self.model_version: str | None = None
        self.error_code: str | None = None
        self.load_error: str | None = None
        self._torch = None
        self._load_model()

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
            import torch
            import torchaudio
            try:
                from model.keyword_cnn import build_model
            except ModuleNotFoundError:
                from backend.model.keyword_cnn import build_model

            self._torch = torch
            del torchaudio
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
            elif (
                getattr(torch.backends, "mps", None) is not None
                and torch.backends.mps.is_available()
            ):
                self.device = torch.device("mps")
            else:
                self.device = torch.device("cpu")
            checkpoint = torch.load(
                self.model_path,
                map_location=self.device,
                weights_only=True,
            )
            if not isinstance(checkpoint, dict):
                raise ValueError("checkpoint must be a dictionary")
            required = {"model_state_dict", "class_names", "model_version"}
            missing = required.difference(checkpoint)
            if missing:
                raise ValueError(f"checkpoint is missing fields: {', '.join(sorted(missing))}")
            class_names = checkpoint["class_names"]
            if list(class_names) != list(CLASS_NAMES) or len(class_names) != NUM_CLASSES:
                raise ValueError("checkpoint class_names do not match training config")
            model = build_model(NUM_CLASSES)
            model.load_state_dict(checkpoint["model_state_dict"])
            model.to(self.device)
            model.eval()
            self.model = model
            self.class_names = list(class_names)
            self.model_version = str(checkpoint["model_version"])
            self.error_code = None
            self.load_error = None
        except ImportError as exc:
            self._set_unavailable(
                "AI_TORCH_UNAVAILABLE",
                f"AI dependencies are not installed: {exc}",
            )
        except Exception as exc:
            self._set_unavailable("AI_MODEL_LOAD_FAILED", f"Unable to load keyword model: {exc}")

    def predict(self, audio_path: str) -> PredictionResult:
        if not self.ready or self.model is None or self._torch is None:
            raise AIUnavailable(self.load_error or "AI model is not ready")
        path = Path(audio_path)
        if not path.is_file():
            raise ValueError(f"Audio file not found: {audio_path}")
        try:
            from training.features import extract_features
        except ModuleNotFoundError:
            from backend.training.features import extract_features

        features = extract_features(str(path)).unsqueeze(0).to(self.device)
        with self._torch.no_grad():
            probabilities = self._torch.softmax(self.model(features), dim=1)
            confidence, class_index = probabilities.max(dim=1)
        confidence_value = float(confidence.item())
        label = self.class_names[int(class_index.item())]
        return PredictionResult(
            label=label,
            confidence=confidence_value,
            accepted=confidence_value >= CONFIDENCE_THRESHOLD,
            model_version=self.model_version or "unknown",
        )
