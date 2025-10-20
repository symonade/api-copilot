import os
from typing import Dict
from .base import ApiAdapter


class SchedulerApi(ApiAdapter):
    def __init__(self):
        super().__init__(
            name=os.getenv("SECONDARY_API_NAME", "scheduler"),
            base_url=os.getenv("SECONDARY_API_BASE_URL", "http://localhost:8001"),
            api_key=os.getenv("SECONDARY_API_KEY"),
        )

    def auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

