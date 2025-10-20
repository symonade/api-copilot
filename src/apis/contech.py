import os
from typing import Dict
from .base import ApiAdapter


class ContechApi(ApiAdapter):
    def __init__(self):
        super().__init__(
            name=os.getenv("PRIMARY_API_NAME", "contech"),
            base_url=os.getenv("PRIMARY_API_BASE_URL", "http://localhost:8000"),
            api_key=os.getenv("PRIMARY_API_KEY"),
        )

    def auth_headers(self) -> Dict[str, str]:
        return {"X-API-Key": self.api_key} if self.api_key else {}

