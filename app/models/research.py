from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator

ResearchType= Literal[
    "daily_brief",
    "deep_report",
    "learning_guide",
    "github_analysis",
]

class ResearchRequest(BaseModel):
    """
        用户提交的研究任务
    """
    topic:str=Field(
        min_length=3,
        max_length=500,
        description="研究主题",
    )

    research_type:ResearchType="deep_report"

    time_start:date|None=None
    time_end:date|None=None

    source_preferences:list[str]=Field(default_factory=list)
    max_sources:int =Field(
        default=20,
        ge=5,
        le=100,
    )

    language:str="zh-CN"
    @model_validator(mode='after')
    def validate_time_range(self)->"ResearchRequest":
        if(
            self.time_start is not None
            and self.time_end is not None
            and self.time_start > self.time_end
        ):
            raise ValueError("time_start must be before time_end")
        return self


class ResearchQuestion(BaseModel):
    """ 
        Planner 生成一个研究的子问题
    """
    question:str=Field(min_length=3,max_length=500)
    goal:str=Field(min_length=3,max_length=500)
    preferred_sources:list[str]=Field(default_factory=list)

class ResearchPlan(BaseModel):
    """
        Planner 的完整结构化输出
    """
    questions:list[ResearchQuestion]=Field(
        min_length=3,
        max_length=5,
    )