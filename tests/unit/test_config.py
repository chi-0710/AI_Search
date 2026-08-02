import pytest
from pydantic import ValidationError

from app.config import Settings

def test_create_default_settings()->None:
    settings=Settings(
        _env_file=None,
    )
    assert settings.app_name=="AI_Search"
    assert settings.default_language=="zh-CN"
    assert settings.default_research_type=="deep_report"
    assert settings.research_min_questions == 3
    assert settings.research_max_questions == 5
    assert settings.research_max_sources == 20

def test_reject_invalid_question_limits()->None:
    with pytest.raises(ValidationError):
        settings=Settings(
            _env_file=None,
            research_min_questions=6,
            research_max_questions=5,
        )

def test_accept_explicit_model_configuration()->None:
    settings = Settings(
        _env_file=None,
        llm_model="deepseek-v4-pro",
        llm_temperature=0.1,
    )

    assert settings.llm_model == "deepseek-v4-pro"
    assert settings.llm_temperature == 0.1