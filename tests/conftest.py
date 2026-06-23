import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeResponse:
    def __init__(self, status_code=200, text="", json_data=None, content=b""):
        self.status_code = status_code
        self.text = text
        self.content = content or text.encode("utf-8")
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class FakeHttp:
    """Routes URLs to canned responses. `routes` maps a substring -> FakeResponse
    (or a callable url->FakeResponse)."""

    def __init__(self, routes=None):
        self.routes = routes or {}
        self.calls = []

    def _match(self, url):
        for key, val in self.routes.items():
            if key in url:
                return val(url) if callable(val) else val
        return None

    def get(self, url, **kwargs):
        self.calls.append(url)
        return self._match(url)

    def get_json(self, url, **kwargs):
        self.calls.append(url)
        resp = self._match(url)
        if resp is None or resp.status_code != 200:
            return None
        try:
            return resp.json()
        except ValueError:
            return None


@pytest.fixture
def fake_http():
    return FakeHttp


@pytest.fixture
def fake_response():
    return FakeResponse
