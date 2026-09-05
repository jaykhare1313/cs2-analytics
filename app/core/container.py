from app.services.interfaces import AnalysisServiceInterface
from app.services.mock_service import MockAnalysisService


analysis_service: AnalysisServiceInterface = MockAnalysisService()


def get_analysis_service() -> AnalysisServiceInterface:
    return analysis_service
