"""Configuration helpers for the SVG render service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


def _get_int_from_env(key: str, default: int) -> int:
    raw_value = os.environ.get(key)
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime settings sourced from environment variables."""

    bucket_name: str = os.environ.get("BUCKET_NAME", "svg-render-service")
    api_key: Optional[str] = os.environ.get("API_KEY")
    signing_service_account: Optional[str] = os.environ.get("SIGNING_SERVICE_ACCOUNT")

    request_timeout_seconds: int = _get_int_from_env("SVG_FETCH_TIMEOUT_SECONDS", 10)
    max_svg_bytes: int = _get_int_from_env("MAX_SVG_BYTES", 5 * 1024 * 1024)

    min_output_width: int = _get_int_from_env("MIN_OUTPUT_WIDTH", 512)
    max_output_width: int = _get_int_from_env("MAX_OUTPUT_WIDTH", 4096)
    max_output_height: int = _get_int_from_env("MAX_OUTPUT_HEIGHT", 4096)

    signed_url_ttl_seconds: int = _get_int_from_env("SIGNED_URL_TTL_SECONDS", 3600)
    prune_after_seconds: int = _get_int_from_env("PRUNE_AFTER_SECONDS", 24 * 3600)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
