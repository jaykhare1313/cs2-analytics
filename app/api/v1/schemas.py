from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl, StringConstraints


Timestamp = Annotated[str, StringConstraints(pattern=r"^(?:\d{2}:\d{2}|\d{2}:\d{2}:\d{2})$")]


class AnalysisRequest(BaseModel):
    url: HttpUrl
    timestamp: Timestamp


class TimelineItem(BaseModel):
    timestamp: str
    critique: str


class AnalysisResponse(BaseModel):
    crosshair_rating: int = Field(ge=1, le=10)
    radar_awareness: str
    movement_accuracy: str
    timeline: list[TimelineItem]
