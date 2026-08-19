import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ai_service import AIService, AIUnavailable


def test_ai_service_imports_without_optional_torch_runtime():
    assert AIService is not None


def test_ai_service_reports_missing_model_without_crashing(tmp_path):
    service = AIService(tmp_path / "missing_keyword_cnn.pt")

    assert service.ready is False
    assert service.error_code in {"AI_MODEL_NOT_FOUND", "AI_TORCH_UNAVAILABLE"}
    assert service.model is None
    assert service.model_version is None


def test_ai_service_rejects_inference_when_model_is_unavailable(tmp_path):
    service = AIService(tmp_path / "missing_keyword_cnn.pt")

    with pytest.raises(AIUnavailable):
        service.predict(str(tmp_path / "sample.wav"))


def test_ai_service_handles_unreadable_checkpoint_without_crashing(tmp_path):
    checkpoint = tmp_path / "keyword_cnn.pt"
    checkpoint.write_bytes(b"not-a-checkpoint")

    service = AIService(checkpoint)

    assert service.ready is False
    assert service.error_code in {"AI_TORCH_UNAVAILABLE", "AI_MODEL_LOAD_FAILED"}
