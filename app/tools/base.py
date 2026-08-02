from email.policy import default
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel, Field, model_validator

ItemT = TypeVar("ItemT")


class ToolResult(BaseModel, Generic[ItemT]):
    """
    The result of a tool execution.
    """
    tool_name: str = Field(min_length=1)
    query: str = Field(min_length=1)

    success: bool
    items: list[ItemT] = Field(default_factory=list)

    error: str | None = None
    duration_ms: float = Field(default=0, ge=0)
    cached: bool = False

    @model_validator(mode="after")
    def validate_result_state(self) -> "ToolResult[ItemT]":
        if self.success and self.error is not None:
            raise ValueError("successful result must not contain an error")

        if not self.success and not self.error:
            raise ValueError("failed result must contain an error")
        return self


class ToolProtocol(Protocol, Generic[ItemT]):
    """
    The protocol for tools.
    """
    async def run(
        self,
        query: str,
    ) -> ToolResult[ItemT]:
        pass
