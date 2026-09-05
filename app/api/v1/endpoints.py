from fastapi import APIRouter, Depends, HTTPException

from app.core.container import get_analysis_service
from app.services.interfaces import AnalysisServiceInterface
from app.api.v1.schemas import AnalysisRequest, AnalysisResponse

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    request: AnalysisRequest,
    service: AnalysisServiceInterface = Depends(get_analysis_service),
) -> AnalysisResponse:
    try:
        result = await service.analyze_video(str(request.url), request.timestamp)
        return AnalysisResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="The video analysis service failed to process the request.",
        ) from exc
