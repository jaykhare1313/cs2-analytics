from abc import ABC, abstractmethod
from typing import Any


class AnalysisServiceInterface(ABC):
    @abstractmethod
    async def analyze_video(self, url: str, timestamp: str) -> dict[str, Any]:
        """Analyze a video at the requested timestamp."""
