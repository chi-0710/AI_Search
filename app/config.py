from functools import lru_cache
from typing import Literal
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnvironment=Literal[
    "development",
    "production",
    "test",
]

class Settings(BaseSettings):
    """
    项目统一配置:
    
    配置优先级:
    1.创建Setting时显式传入的参数
    2.系统环境变量
    3. .env 文件
    4.当前类中的默认值
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================
    # 应用配置
    # =========================================================
    app_name:str="AI_Search"
    app_env:AppEnvironment="development"
    app_debug:bool=True
    log_level:str="INFO"

    default_language:str ="zh-CN"
    default_research_type:str="deep_report"

    # =========================================================
    # 研究任务配置
    # =========================================================
    research_min_questions: int = Field(default=3, ge=1, le=10)
    research_max_questions: int = Field(default=5, ge=1, le=10)

    research_max_sources: int = Field(default=20, ge=5, le=100)
    research_max_concurrency: int = Field(default=5, ge=1, le=20)
    research_task_timeout_seconds: int = Field(default=300, ge=10)

    research_max_revisions: int = Field(default=2, ge=0, le=5)

    # =========================================================
    # LLM 配置
    # =========================================================
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-v4-flash"

    llm_temperature: float = Field(default=0.2, ge=0, le=2)
    llm_timeout_seconds: int = Field(default=60, ge=1)
    llm_max_retries: int = Field(default=2, ge=0, le=10)
    llm_max_tokens: int = Field(default=8192, ge=256)

    # =========================================================
    # DeepSeek
    # =========================================================
    deepseek_api_key: SecretStr | None = None
    deepseek_api_base: str = "https://api.deepseek.com/v1"

    # =========================================================
    # Web Search
    # =========================================================
    web_search_provider: str = ""
    web_search_api_key: SecretStr | None = None
    web_search_timeout_seconds: int = Field(default=20, ge=1)
    web_search_max_retries: int = Field(default=2, ge=0, le=10)
    web_search_max_results: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def validate_question_limits(self) -> "Settings":
        """确保 Planner 最小问题数不大于最大问题数。"""

        if self.research_min_questions > self.research_max_questions:
            raise ValueError(
                "research_min_questions must be less than or equal to "
                "research_max_questions"
            )

        return self


@lru_cache
def get_settings() -> Settings:
    """
    获取全局配置。

    lru_cache 可以避免每个模块反复读取 .env 文件。
    """

    return Settings()
