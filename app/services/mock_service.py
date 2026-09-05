from copy import deepcopy
from typing import Any

from app.services.interfaces import AnalysisServiceInterface


MOCK_ANALYSIS: dict[str, Any] = {
    "crosshair_rating": 7,
    "radar_awareness": (
        "You checked radar after the first contact, but the second check came too late "
        "to confirm the connector rotate. Build a habit of checking during utility travel."
    ),
    "movement_accuracy": (
        "Counter-strafes are reliable when clearing close angles, though the wide swing "
        "from default into jungle was off-tempo and left you exposed before the trade."
    ),
    "timeline": [
        {
            "timestamp": "01:12",
            "critique": (
                "On Mirage A ramp, your crosshair is a head level too low as you clear "
                "ticket. Raise it before the swing so the first bullet is ready for a "
                "ticket player instead of the floor."
            ),
        },
        {
            "timestamp": "01:28",
            "critique": (
                "After the jungle smoke blooms, take the half-second radar check before "
                "committing to default. It would have shown your short player was still "
                "two steps away from the trade."
            ),
        },
        {
            "timestamp": "01:41",
            "critique": (
                "You over-peeked from default into the jungle angle while exposed to "
                "ticket. Hold the smoke edge or isolate jungle first; the extra step "
                "created a duel with no teammate able to trade."
            ),
        },
        {
            "timestamp": "01:56",
            "critique": (
                "The entry kill was clean, but the follow-up swing was off-tempo. Pause "
                "for the flash and let your short teammate close distance before taking "
                "the second duel."
            ),
        },
    ],
}


class MockAnalysisService(AnalysisServiceInterface):
    async def analyze_video(self, url: str, timestamp: str) -> dict[str, Any]:
        return deepcopy(MOCK_ANALYSIS)
