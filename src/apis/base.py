import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ApiAdapter(ABC):
    """Minimal interface for each external API."""

    def __init__(self, name: str, base_url: str, api_key: Optional[str] = None):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @abstractmethod
    def auth_headers(self) -> Dict[str, str]:
        ...

    def with_base(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"


class ApiRegistry:
    """Holds API adapters and a simple selection policy."""

    def __init__(self):
        self._apis: Dict[str, ApiAdapter] = {}

    def register(self, adapter: ApiAdapter):
        self._apis[adapter.name] = adapter

    def get(self, name: str) -> Optional[ApiAdapter]:
        return self._apis.get(name)

    def all(self) -> Dict[str, ApiAdapter]:
        return dict(self._apis)

    def select_for_query(self, query: str) -> ApiAdapter:
        """
        Heuristic router:
        - schedule/timeline/calendar/deadline -> secondary ('scheduler')
        - project/cost/auth/key -> primary ('contech')
        - else -> primary
        """
        q = (query or "").lower()
        secondary = os.getenv("SECONDARY_API_NAME", "scheduler")
        primary = os.getenv("PRIMARY_API_NAME", "contech")
        if any(k in q for k in ["schedule", "calendar", "timeline", "deadline"]):
            return self._apis.get(secondary) or next(iter(self._apis.values()))
        if any(k in q for k in ["project", "cost", "authenticate", "auth", "key"]):
            return self._apis.get(primary) or next(iter(self._apis.values()))
        return self._apis.get(primary) or next(iter(self._apis.values()))

