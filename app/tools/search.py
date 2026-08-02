import asyncio
import hashlib
import logging
import time
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import Settings, get_settings
from app.models.source import SourceDocument
from app.tools.base import ToolProtocol, ToolResult

logger = logging.getLogger(__name__)

SearchDepth = Literal[
    "basic",
    "advanced",
    "fast",
    "ultra-fast",
]

SearchTopic = Literal[
    "general",
    "news",
    "finance",
]

TAVILY_SEARCH_URL = "https://api.tavily.com/search"

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
}


class InvalidSearchResponseError(ValueError):
    """Tavily 返回了无法解析的响应。"""


class TavilySearchParams(BaseModel):
    """经过标准化和校验的 Tavily 搜索参数。"""

    query: str = Field(
        min_length=1,
        max_length=400,
    )

    max_results: int = Field(
        default=10,
        ge=1,
        le=20,
    )

    topic: SearchTopic = "general"
    search_depth: SearchDepth = "basic"

    include_domains: list[str] = Field(
        default_factory=list,
        max_length=300,
    )

    exclude_domains: list[str] = Field(
        default_factory=list,
        max_length=150,
    )

    start_date: date | None = None
    end_date: date | None = None

    @field_validator("query", mode="before")
    @classmethod
    def normalize_query(
        cls,
        value: Any,
    ) -> Any:
        if isinstance(value, str):
            return " ".join(value.split())

        return value

    @field_validator(
        "include_domains",
        "exclude_domains",
    )
    @classmethod
    def normalize_domains(
        cls,
        domains: list[str],
    ) -> list[str]:
        normalized_domains: list[str] = []
        seen: set[str] = set()

        for raw_domain in domains:
            candidate = raw_domain.strip().lower()

            if not candidate:
                continue

            # 同时允许用户传入域名或完整 URL。
            value_for_parsing = candidate if "://" in candidate else f"//{candidate}"

            parsed = urlsplit(value_for_parsing)
            domain = parsed.hostname

            if not domain:
                raise ValueError(f"invalid domain: {raw_domain}")

            domain = domain.rstrip(".")

            if domain in seen:
                continue

            seen.add(domain)
            normalized_domains.append(domain)

        return normalized_domains

    @model_validator(mode="after")
    def validate_parameter_relationships(
        self,
    ) -> "TavilySearchParams":
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date must be before or equal to end_date")

        overlap = set(self.include_domains) & set(self.exclude_domains)

        if overlap:
            duplicated = ", ".join(sorted(overlap))
            raise ValueError(
                "the same domain cannot be included and " f"excluded: {duplicated}"
            )

        return self

    def to_payload(self) -> dict[str, Any]:
        """转换为 Tavily Search API 请求体。"""

        payload: dict[str, Any] = {
            "query": self.query,
            "search_depth": self.search_depth,
            "max_results": self.max_results,
            "topic": self.topic,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }

        if self.include_domains:
            payload["include_domains"] = self.include_domains

        if self.exclude_domains:
            payload["exclude_domains"] = self.exclude_domains

        if self.start_date is not None:
            payload["start_date"] = self.start_date.isoformat()

        if self.end_date is not None:
            payload["end_date"] = self.end_date.isoformat()

        return payload


def is_tracking_query_key(key: str) -> bool:
    normalized = key.lower()

    return normalized.startswith("utm_") or normalized in TRACKING_QUERY_KEYS


def canonicalize_url(raw_url: str) -> str:
    """
    生成用于初步去重的规范化 URL。

    处理内容：
    - scheme 和 host 转成小写；
    - 移除 fragment；
    - 移除常见跟踪参数；
    - 对剩余查询参数排序；
    - 移除默认端口；
    - 统一路径末尾斜杠。
    """

    candidate = raw_url.strip()
    parsed = urlsplit(candidate)

    scheme = parsed.scheme.lower()

    if scheme not in {"http", "https"}:
        raise ValueError(f"unsupported URL scheme: {raw_url}")

    if not parsed.hostname:
        raise ValueError(f"URL does not contain a hostname: {raw_url}")

    if parsed.username or parsed.password:
        raise ValueError("URL must not contain user information")

    hostname = parsed.hostname.encode("idna").decode("ascii").lower()

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"invalid URL port: {raw_url}") from exc

    if (
        port is None
        or scheme == "http"
        and port == 80
        or scheme == "https"
        and port == 443
    ):
        netloc = hostname
    else:
        netloc = f"{hostname}:{port}"

    path = parsed.path or "/"

    if path != "/":
        path = path.rstrip("/")

    query_items = [
        (key, value)
        for key, value in parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
        if not is_tracking_query_key(key)
    ]

    query_items.sort()
    normalized_query = urlencode(query_items)

    return urlunsplit(
        (
            scheme,
            netloc,
            path,
            normalized_query,
            "",
        )
    )


def build_source_id(canonical_url: str) -> str:
    digest = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()

    return f"web_{digest[:16]}"


def build_content_hash(content: str) -> str | None:
    normalized = content.strip()

    if not normalized:
        return None

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def parse_published_at(
    value: Any,
) -> datetime | None:
    if not isinstance(value, str):
        return None

    candidate = value.strip()

    if not candidate:
        return None

    # 首先尝试 ISO 8601。
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        parsed = None

    # Tavily 新闻结果也可能返回 RFC 2822 格式。
    if parsed is None:
        try:
            parsed = parsedate_to_datetime(candidate)
        except (TypeError, ValueError):
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def as_clean_text(value: Any) -> str:
    """
    将值转换为清理后的文本。
    """
    if isinstance(value, str):
        return value.strip()

    return ""


class TavilySearchTool(ToolProtocol[SourceDocument]):
    """
    The Tavily search tool.
    """
    name = "tavily_search"

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 20,
        max_retries: int = 2,
        default_max_results: int = 10,
        retry_delay_seconds: float = 0.25,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        normalized_api_key = api_key.strip()

        if not normalized_api_key:
            raise ValueError("Tavily API key must not be empty")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")

        if not 1 <= default_max_results <= 20:
            raise ValueError("default_max_results must be between 1 and 20")

        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be non-negative")

        self._api_key = normalized_api_key
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._default_max_results = default_max_results
        self._retry_delay_seconds = retry_delay_seconds

        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds)
        )

    async def run(
        self,
        query: str,
    ) -> ToolResult[SourceDocument]:
        """
        实现 ToolProtocol 需要的基础接口。

        如果需要日期、域名等高级参数，
        可以直接调用 search()。
        """

        params = TavilySearchParams(
            query=query,
            max_results=self._default_max_results,
        )

        return await self.search(params)

    async def search(
        self,
        params: TavilySearchParams,
    ) -> ToolResult[SourceDocument]:
        started_at = time.perf_counter()

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post(
                    TAVILY_SEARCH_URL,
                    headers={
                        "Authorization": (f"Bearer {self._api_key}"),
                        "Content-Type": "application/json",
                    },
                    json=params.to_payload(),
                    timeout=self._timeout_seconds,
                )

                response.raise_for_status()

                raw_payload: Any = response.json()

                if not isinstance(raw_payload, dict):
                    raise InvalidSearchResponseError("response root must be an object")

                items = self._parse_results(
                    payload=raw_payload,
                    params=params,
                )

                return self._success_result(
                    query=params.query,
                    items=items,
                    started_at=started_at,
                )

            except httpx.TimeoutException:
                if attempt < self._max_retries:
                    await self._wait_before_retry(attempt)
                    continue

                logger.warning(
                    "Tavily request timed out after %s attempts",
                    attempt + 1,
                )

                return self._failure_result(
                    query=params.query,
                    error="tavily request timed out",
                    started_at=started_at,
                )

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                if (
                    self._is_retryable_status(status_code)
                    and attempt < self._max_retries
                ):
                    await self._wait_before_retry(attempt)
                    continue

                logger.warning(
                    "Tavily returned HTTP %s",
                    status_code,
                )

                return self._failure_result(
                    query=params.query,
                    error=self._http_error_message(status_code),
                    started_at=started_at,
                )

            except httpx.RequestError:
                if attempt < self._max_retries:
                    await self._wait_before_retry(attempt)
                    continue

                logger.warning(
                    "Tavily network request failed",
                    exc_info=True,
                )

                return self._failure_result(
                    query=params.query,
                    error="tavily network request failed",
                    started_at=started_at,
                )

            except (
                InvalidSearchResponseError,
                TypeError,
                ValueError,
            ):
                logger.warning(
                    "Tavily returned an invalid response",
                    exc_info=True,
                )

                return self._failure_result(
                    query=params.query,
                    error=("tavily returned an invalid response"),
                    started_at=started_at,
                )

        # 理论上不会执行到这里。
        return self._failure_result(
            query=params.query,
            error="tavily search failed",
            started_at=started_at,
        )

    def _parse_results(
        self,
        *,
        payload: dict[str, Any],
        params: TavilySearchParams,
    ) -> list[SourceDocument]:
        raw_results = payload.get("results")

        if not isinstance(raw_results, list):
            raise InvalidSearchResponseError("results must be a list")

        if not raw_results:
            # 空结果不是异常，搜索请求本身仍然成功。
            return []

        request_id = as_clean_text(payload.get("request_id"))

        documents_by_url: dict[
            str,
            SourceDocument,
        ] = {}

        for index, raw_result in enumerate(raw_results):
            if not isinstance(raw_result, dict):
                logger.warning(
                    "Ignoring invalid Tavily result at index %s",
                    index,
                )
                continue

            try:
                document = self._build_document(
                    raw_result=raw_result,
                    query=params.query,
                    request_id=request_id,
                    result_index=index,
                )
            except (ValueError, TypeError):
                logger.warning(
                    "Ignoring malformed Tavily result at index %s",
                    index,
                    exc_info=True,
                )
                continue

            canonical_url = as_clean_text(document.metadata.get("canonical_url"))

            existing = documents_by_url.get(canonical_url)

            if existing is None:
                documents_by_url[canonical_url] = document
                continue

            existing_score = float(existing.metadata.get("score", 0))
            candidate_score = float(document.metadata.get("score", 0))

            # 同一 URL 保留相关性分数更高的结果。
            if candidate_score > existing_score:
                documents_by_url[canonical_url] = document

        if not documents_by_url:
            raise InvalidSearchResponseError("response contained no valid results")

        documents = list(documents_by_url.values())

        documents.sort(
            key=lambda document: float(document.metadata.get("score", 0)),
            reverse=True,
        )

        return documents[: params.max_results]

    @staticmethod
    def _build_document(
        *,
        raw_result: dict[str, Any],
        query: str,
        request_id: str,
        result_index: int,
    ) -> SourceDocument:
        """
        Build a document from a Tavily search result.
        """
        raw_url = as_clean_text(raw_result.get("url"))

        canonical_url = canonicalize_url(raw_url)

        title = as_clean_text(raw_result.get("title"))

        if not title:
            title = urlsplit(canonical_url).hostname or canonical_url

        content = as_clean_text(raw_result.get("content"))

        raw_content = as_clean_text(raw_result.get("raw_content"))

        summary = content or raw_content[:1000]

        raw_score = raw_result.get("score", 0)

        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 0.0

        raw_published_date = raw_result.get("published_date")

        metadata: dict[str, Any] = {
            "provider": "tavily",
            "search_query": query,
            "score": score,
            "canonical_url": canonical_url,
            "request_id": request_id,
            "provider_result_index": result_index,
        }

        if isinstance(raw_published_date, str):
            metadata["raw_published_date"] = raw_published_date

        content_for_hash = raw_content or content

        return SourceDocument(
            source_id=build_source_id(canonical_url),
            title=title,
            url=canonical_url,
            source_type="web",
            published_at=parse_published_at(raw_published_date),
            summary=summary,
            # T07 默认不请求整页正文。
            clean_content=raw_content,
            content_hash=build_content_hash(content_for_hash),
            metadata=metadata,
        )

    async def _wait_before_retry(
        self,
        attempt: int,
    ) -> None:
        delay = self._retry_delay_seconds * 2**attempt

        if delay > 0:
            await asyncio.sleep(delay)

    @staticmethod
    def _is_retryable_status(
        status_code: int,
    ) -> bool:
        return status_code in {408, 425, 429} or status_code >= 500

    @staticmethod
    def _http_error_message(
        status_code: int,
    ) -> str:
        if status_code == 401:
            return "tavily authentication failed"

        if status_code == 429:
            return "tavily rate limit exceeded"

        if status_code in {432, 433}:
            return "tavily usage quota exceeded"

        if status_code >= 500:
            return "tavily service unavailable"

        return "tavily request failed " f"with HTTP {status_code}"

    def _success_result(
        self,
        *,
        query: str,
        items: list[SourceDocument],
        started_at: float,
    ) -> ToolResult[SourceDocument]:
        return ToolResult[SourceDocument](
            tool_name=self.name,
            query=query,
            success=True,
            items=items,
            duration_ms=self._duration_ms(started_at),
        )

    def _failure_result(
        self,
        *,
        query: str,
        error: str,
        started_at: float,
    ) -> ToolResult[SourceDocument]:
        return ToolResult[SourceDocument](
            tool_name=self.name,
            query=query,
            success=False,
            error=error,
            duration_ms=self._duration_ms(started_at),
        )

    @staticmethod
    def _duration_ms(
        started_at: float,
    ) -> float:
        return max(
            0,
            (time.perf_counter() - started_at) * 1000,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def build_tavily_search_tool(
    settings: Settings | None = None,
) -> TavilySearchTool:
    """根据项目配置创建 Tavily 搜索工具。"""

    resolved_settings = settings or get_settings()

    provider = resolved_settings.web_search_provider.strip().lower()

    if provider != "tavily":
        raise RuntimeError("WEB_SEARCH_PROVIDER must be configured " "as 'tavily'")

    secret = resolved_settings.web_search_api_key

    if secret is None:
        raise RuntimeError("WEB_SEARCH_API_KEY is not configured")

    api_key = secret.get_secret_value().strip()

    if not api_key:
        raise RuntimeError("WEB_SEARCH_API_KEY is empty")

    # Settings 允许配置到 100，但 Tavily 单次请求
    # 当前最大只支持 20，因此这里做 Provider 适配。
    default_max_results = min(
        resolved_settings.web_search_max_results,
        20,
    )

    return TavilySearchTool(
        api_key=api_key,
        timeout_seconds=(resolved_settings.web_search_timeout_seconds),
        max_retries=(resolved_settings.web_search_max_retries),
        default_max_results=default_max_results,
    )
