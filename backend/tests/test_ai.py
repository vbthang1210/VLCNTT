import pytest

from app.services.ai_service import AIService, AIUnavailable


def test_ai_service_import():
    assert AIService is not None


def test_ai_service_reports_missing_model_without_crashing(tmp_path):
    service = AIService(tmp_path / "missing_keyword_cnn.pt")

    assert service.ready is False
    assert service.error_code == "AI_MODEL_NOT_FOUND"
    assert service.model is None
    assert service.model_version is None


def test_ai_service_rejects_inference_when_model_is_unavailable(tmp_path):
    service = AIService(tmp_path / "missing_keyword_cnn.pt")

    with pytest.raises(AIUnavailable, match="Keyword model not found"):
        service.predict(str(tmp_path / "sample.wav"))
