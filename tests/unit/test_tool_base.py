import pytest
from pydantic import BaseModel, ValidationError
from app.tools.base import ToolResult

class FakeItem(BaseModel):
    title:str
    url:str

@pytest.mark.unit
def test_create_success_result()->None:
    result=ToolResult[FakeItem](
        tool_name="fake_tool",
        query="fake_query",
        success=True,
        items=[
            FakeItem(
                title="fake_title", 
                url="fake_url"
                )
            ],
        duration_ms=12.5,
    )

    assert result.success is True
    assert result.error is None
    assert len(result.items) == 1
    assert result.cached is False

@pytest.mark.unit
def test_create_failure_result() -> None:
    result = ToolResult[FakeItem](
        tool_name="fake_search",
        query="LangGraph updates",
        success=False,
        error="request timeout",
        duration_ms=1000,
    )

    assert result.success is False
    assert result.items == []
    assert result.error == "request timeout"


@pytest.mark.unit
def test_reject_success_with_error() -> None:
    with pytest.raises(ValidationError):
        ToolResult[FakeItem](
            tool_name="fake_search",
            query="LangGraph updates",
            success=True,
            error="unexpected error",
        )


@pytest.mark.unit
def test_reject_failure_without_error() -> None:
    with pytest.raises(ValidationError):
        ToolResult[FakeItem](
            tool_name="fake_search",
            query="LangGraph updates",
            success=False,
        )


@pytest.mark.unit
def test_reject_negative_duration() -> None:
    with pytest.raises(ValidationError):
        ToolResult[FakeItem](
            tool_name="fake_search",
            query="LangGraph updates",
            success=True,
            duration_ms=-1,
        )