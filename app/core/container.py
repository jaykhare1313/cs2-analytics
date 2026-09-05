from app.services.interfaces import AnalysisServiceInterface
from app.core.config import get_settings
from app.services.gemini_service import GeminiAnalysisService
from app.services.mock_service import MockAnalysisService


settings = get_settings()
analysis_service: AnalysisServiceInterface = (
    GeminiAnalysisService() if settings.analysis_backend == "gemini" else MockAnalysisService()
)


def get_analysis_service() -> AnalysisServiceInterface:
    return analysis_service
