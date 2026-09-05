import asyncio
import glob
import subprocess
import tempfile
from pathlib import Path

import yt_dlp
from google import genai

from app.api.v1.schemas import AnalysisResponse
from app.core.config import get_settings
from app.services.interfaces import AnalysisServiceInterface

FRAME_INTERVAL_SECONDS = 5
DOWNLOAD_TIMEOUT_SECONDS = 60
FFMPEG_TIMEOUT_SECONDS = 30
GEMINI_TIMEOUT_SECONDS = 60

SYSTEM_PROMPT = """
Act as a blunt but constructive Counter-Strike 2 coach. Analyze the player's
first-person gameplay clip from the supplied frames, which are sampled at fixed
time intervals. Each image is preceded by a text label stating the exact MM:SS
timestamp at which that frame was captured in the clip.

Evaluate crosshair placement and pre-aim habits, radar/minimap awareness
(including callouts, rotations, and checking corners), and movement accuracy
(including peek technique, counter-strafing, and over-extension). Be specific
about what is visible in the frames rather than giving generic advice.

Return a crosshair_rating integer from 1 to 10. Every timeline entry's
timestamp must be one of the exact MM:SS labels provided for the frames; never
invent a time. Use a blunt but constructive coaching tone.
""".strip()


def _download(url: str, out_dir: Path) -> Path:
    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": str(out_dir / "video.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": DOWNLOAD_TIMEOUT_SECONDS,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        downloader.download([url])

    matches = glob.glob(str(out_dir / "video.*"))
    if not matches:
        raise RuntimeError("yt-dlp did not produce an output file")
    return Path(matches[0])


def _extract_frames(video_path: Path, out_dir: Path) -> list[Path]:
    subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            f"fps=1/{FRAME_INTERVAL_SECONDS}",
            "-q:v",
            "2",
            str(out_dir / "frame_%03d.jpg"),
        ],
        check=True,
        capture_output=True,
        timeout=FFMPEG_TIMEOUT_SECONDS,
    )
    frames = sorted(out_dir.glob("frame_*.jpg"))
    if not frames:
        raise RuntimeError("ffmpeg produced no frames")
    return frames


class GeminiAnalysisService(AnalysisServiceInterface):
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = genai.Client(api_key=self._settings.gemini_api_key)

    async def analyze_video(self, url: str, timestamp: str) -> dict:
        del timestamp
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                temp_dir = Path(temporary_directory)
                video_path = await asyncio.to_thread(_download, url, temp_dir)
                frame_paths = await asyncio.to_thread(
                    _extract_frames,
                    video_path,
                    temp_dir,
                )

                def format_timestamp(seconds: int) -> str:
                    minutes, remaining_seconds = divmod(seconds, 60)
                    return f"{minutes:02d}:{remaining_seconds:02d}"

                labels = [
                    format_timestamp(index * FRAME_INTERVAL_SECONDS)
                    for index in range(len(frame_paths))
                ]
                contents: list[object] = []
                for frame_path, label in zip(frame_paths, labels):
                    contents.append(f"Frame at {label}:")
                    contents.append(
                        genai.types.Part.from_bytes(
                            data=frame_path.read_bytes(),
                            mime_type="image/jpeg",
                        )
                    )

                def _call_gemini():
                    return self._client.models.generate_content(
                        model=self._settings.gemini_model,
                        contents=contents,
                        config={
                            "system_instruction": SYSTEM_PROMPT,
                            "response_mime_type": "application/json",
                            "response_schema": AnalysisResponse,
                        },
                    )

                response = await asyncio.wait_for(
                    asyncio.to_thread(_call_gemini),
                    timeout=GEMINI_TIMEOUT_SECONDS,
                )
                if response.parsed is None:
                    raise RuntimeError("Gemini returned no parsed analysis")
                return response.parsed.model_dump()
        except Exception as exc:
            raise RuntimeError(f"Gemini analysis failed: {exc}") from exc
