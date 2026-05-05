from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    XAI = "xai"
    OTHER = "other"


class Tool(StrEnum):
    CLAUDE_CODE = "claude_code"
    CURSOR = "cursor"
    CODEX = "codex"
    OTHER = "other"


class ReportSource(StrEnum):
    CODEX_LOCAL_TELEMETRY = "codex_local_telemetry"
    TOOL_STATS_PASTE = "tool_stats_paste"
    LOCAL_LOG = "local_log"
    CSV = "csv"
    JSON = "json"
    MANUAL = "manual"
    SCREENSHOT_OCR = "screenshot_ocr"
    RESPONSE_LOG = "response_log"


class PeriodWidth(StrEnum):
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1m"
    CUSTOM = "custom"


class CostSource(StrEnum):
    PROVIDER_ACTUAL = "provider_actual"
    PROVIDER_REPORT = "provider_report"
    ESTIMATED = "estimated"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: str | None = None
    adapter_version: str | None = None
    row_count: int | None = Field(default=None, ge=0)
    dedupe_key: str | None = None
    query_fingerprint: str | None = None
    warnings: list[str] = Field(default_factory=list)


class UsageReportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Provider
    tool: Tool | None = None
    source: ReportSource
    period_start: datetime
    period_end: datetime
    period_width: PeriodWidth
    model: str | None = None
    request_count: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    cache_creation_input_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    cost_source: CostSource
    confidence: Confidence
    evidence: EvidenceMetadata | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_sensitive_input(cls, data):
        if isinstance(data, dict):
            reject_sensitive_fields(data)
        return data

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "UsageReportRow":
        if self.period_end <= self.period_start:
            raise ValueError("period_end must be after period_start")
        if self.total_tokens is None:
            parts = [
                self.input_tokens,
                self.output_tokens,
                self.cached_input_tokens,
                self.cache_creation_input_tokens,
                self.reasoning_tokens,
            ]
            known_parts = [part for part in parts if part is not None]
            if known_parts:
                self.total_tokens = sum(known_parts)
        if self.source == ReportSource.MANUAL:
            self.confidence = Confidence.LOW
        return self


class ReportWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Provider | None = None
    tool: Tool | None = None
    code: str
    message: str


class UserConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_shown: bool
    confirmed_at: datetime


class UsageReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_session_id: str
    generated_at: datetime
    schema_version: Literal["2026-05-04"] = "2026-05-04"
    rows: list[UsageReportRow]
    warnings: list[ReportWarning] = Field(default_factory=list)
    user_confirmation: UserConfirmation

    @model_validator(mode="before")
    @classmethod
    def reject_sensitive_input(cls, data):
        if isinstance(data, dict):
            reject_sensitive_fields(data)
        return data

    @model_validator(mode="after")
    def require_preview_before_submit(self) -> "UsageReportPayload":
        if not self.user_confirmation.preview_shown:
            raise ValueError("preview must be shown before confirmation")
        return self


SENSITIVE_FIELD_NAMES = {
    "prompt",
    "prompts",
    "response",
    "responses",
    "conversation",
    "conversation_history",
    "api_key",
    "secret",
    "environment",
    "env",
    "source_code",
    "raw_log",
}


def reject_sensitive_fields(data: dict[str, Any]) -> None:
    found = _find_sensitive_fields(data)
    if found:
        names = ", ".join(sorted(found))
        raise ValueError(f"sensitive fields are not allowed: {names}")


def _find_sensitive_fields(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in SENSITIVE_FIELD_NAMES:
                found.add(normalized)
            found.update(_find_sensitive_fields(nested))
    elif isinstance(value, list):
        for item in value:
            found.update(_find_sensitive_fields(item))
    return found
