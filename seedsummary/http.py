"""Shared HTTP session with retries and a configurable timeout/UA."""
from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

log = logging.getLogger("seedsummary.http")

_DEFAULT_UA = "seed-summary/1.0 (+https://github.com/raisabehal/seed-summary)"


class Http:
    def __init__(self, user_agent: str = _DEFAULT_UA, timeout: int = 25, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "*/*"})

    @classmethod
    def from_config(cls, http_cfg: dict[str, Any]) -> "Http":
        http_cfg = http_cfg or {}
        return cls(
            user_agent=http_cfg.get("user_agent", _DEFAULT_UA),
            timeout=int(http_cfg.get("timeout_seconds", 25)),
            max_retries=int(http_cfg.get("max_retries", 3)),
        )

    def get(self, url: str, **kwargs: Any) -> Optional[requests.Response]:
        """GET with retries. Returns None on persistent failure (never raises),
        so one dead source can't abort the whole weekly run."""
        try:
            return self._get_with_retry(url, **kwargs)
        except Exception as exc:  # noqa: BLE001 - resilience is the point
            log.warning("GET failed for %s: %s", url, exc)
            return None

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    )
    def _get_with_retry(self, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        resp = self.session.get(url, **kwargs)
        # Retry on transient server errors; treat 4xx as terminal.
        if resp.status_code >= 500:
            raise requests.ConnectionError(f"{resp.status_code} from {url}")
        return resp

    def get_json(self, url: str, **kwargs: Any) -> Any:
        resp = self.get(url, **kwargs)
        if resp is None or resp.status_code != 200:
            return None
        try:
            return resp.json()
        except ValueError:
            return None
