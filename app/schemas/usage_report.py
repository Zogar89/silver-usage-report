from datetime import datetime
from enum import StrEnum
import re
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
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: str | None = Field(default=None, max_length=80)
    adapter_version: str | None = Field(default=None, max_length=80)
    row_count: int | None = Field(default=None, ge=0)
    dedupe_key: str | None = Field(default=None, max_length=120)
    query_fingerprint: str | None = Field(default=None, max_length=120)
    model_context_window: int | None = Field(default=None, ge=0)
    plan_type: str | None = Field(default=None, max_length=120)
    rate_limit_primary_used_percent: float | None = Field(default=None, ge=0)
    rate_limit_secondary_used_percent: float | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list, max_length=50)


class UsageReportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Provider
    tool: Tool | None = None
    source: ReportSource
    period_start: datetime
    period_end: datetime
    period_width: PeriodWidth
    model: str | None = Field(default=None, max_length=120)
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
        return self


class ReportWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Provider | None = None
    tool: Tool | None = None
    code: str = Field(max_length=120)
    message: str = Field(max_length=1000)


class UserConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_shown: bool
    confirmed_at: datetime


class UsageReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_session_id: str
    generated_at: datetime
    schema_version: Literal["2026-05-04"] = "2026-05-04"
    rows: list[UsageReportRow] = Field(min_length=1, max_length=500)
    warnings: list[ReportWarning] = Field(default_factory=list, max_length=100)
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

SENSITIVE_FIELD_ALIASES = {
    "apikey",
    "apiKey".lower(),
    "api_key",
    "prompttext",
    "prompt_text",
    "responsetext",
    "response_text",
    "rawlog",
    "raw_log",
    "sourcecode",
    "source_code",
}

SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\bapi[_-]?key\b", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{6,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(raw[_ -]?log|source[_ -]?code|conversation[_ -]?history)\b", re.IGNORECASE),
)


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
            compact = re.sub(r"[^a-z0-9]", "", normalized)
            if normalized in SENSITIVE_FIELD_NAMES or normalized in SENSITIVE_FIELD_ALIASES or compact in SENSITIVE_FIELD_ALIASES:
                found.add(normalized)
            found.update(_find_sensitive_fields(nested))
    elif isinstance(value, list):
        for item in value:
            found.update(_find_sensitive_fields(item))
    elif isinstance(value, str):
        for pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(value):
                found.add("sensitive_value")
                break
    return found
