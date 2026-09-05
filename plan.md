# Prompt for Cursor: Add Real Analysis (YouTube fetch + Gemini vision) to cs2-analytics

This is a follow-up to the existing `cs2-analytics` scaffold (FastAPI + uv + pyproject.toml,
with `AnalysisServiceInterface`, `MockAnalysisService`, and `container.py` already in place).
Do not change the existing schemas, router, or main.py structure — only add and modify the
files listed below. No test files. No placeholders or `# implement later` comments.

## What this feature does

`/api/v1/analyze` currently always returns mock data. After this change, the app must be able
to run a REAL analysis pipeline:

1. Download the YouTube video at the given `url` (it is already a ~1 minute clip — do not
   trim or slice it).
2. Extract still frames from it at fixed intervals using `ffmpeg`.
3. Send all frames in a single request to Google's Gemini API (free tier), asking it to act
   as a CS2 coach and return JSON matching the exact `AnalysisResponse` schema.
4. Validate and return that response.

The existing `MockAnalysisService` must remain in the codebase, unchanged, and usable — this
feature adds a second implementation of `AnalysisServiceInterface`, it does not replace the
mock. Which one runs is controlled by a setting (see `container.py` changes below), so the
app can fall back to mock data if no Gemini API key is configured.

## Files to modify or create

```
cs2-analytics/
├── pyproject.toml                    (MODIFY — add 2 dependencies)
├── .env.example                      (MODIFY — add 3 new variables)
└── app/
    ├── core/
    │   ├── config.py                 (MODIFY — add 3 new settings)
    │   └── container.py              (MODIFY — backend switch)
    └── services/
        └── gemini_service.py         (CREATE — new file)
```

## `pyproject.toml` changes

Add these two dependencies to the existing `[project]` dependencies list, alongside the ones
already there. Use these exact version constraints (not exact pins — these packages ship
frequent releases and exact pins go stale fast):

```
"google-genai>=2.0.0,<3.0.0"
"yt-dlp>=2026.1.1"
```

Do not touch any other dependency already listed.

## `.env.example` changes

Add these three lines (keep the existing `APP_NAME`, `APP_VERSION`, `CORS_ORIGINS` lines
exactly as they are):

```
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
ANALYSIS_BACKEND=mock
```

`ANALYSIS_BACKEND` defaults to `mock` so the app runs out of the box with zero API keys.
Setting it to `gemini` in a real `.env` file switches to the live pipeline.

## `app/core/config.py` changes

Add three new fields to the existing `Settings(BaseSettings)` class, alongside the existing
`app_name`, `app_version`, `cors_origins` fields:

- `gemini_api_key: str = ""` — read from `GEMINI_API_KEY`
- `gemini_model: str = "gemini-2.5-flash"` — read from `GEMINI_MODEL`
- `analysis_backend: str = "mock"` — read from `ANALYSIS_BACKEND`

Do not remove or rename any existing field. `get_settings()` stays as-is (still cached via
`functools.lru_cache`).

## `app/core/container.py` changes

Currently this file instantiates `MockAnalysisService` once at module load and exposes
`get_analysis_service()`. Change it to choose the implementation based on
`settings.analysis_backend`:

- If `settings.analysis_backend == "gemini"`, instantiate and return `GeminiAnalysisService`
  (imported from `app.services.gemini_service`)
- Otherwise (any other value, including the default `"mock"`), instantiate and return
  `MockAnalysisService` — this is the safe fallback

Do this instantiation once at module load (singleton), exactly like the current pattern —
do not create a new instance per request. `get_analysis_service()` keeps the same signature
and return type (`AnalysisServiceInterface`) so `app/api/v1/endpoints.py` needs zero changes.

## `app/services/gemini_service.py` — full specification

Create `GeminiAnalysisService(AnalysisServiceInterface)` implementing
`async def analyze_video(self, url: str, timestamp: str) -> dict`. Follow this exact
implementation approach:

### Imports and setup
```python
import asyncio
import glob
import subprocess
import tempfile
from pathlib import Path

from google import genai

from app.api.v1.schemas import AnalysisResponse
from app.core.config import get_settings
from app.services.interfaces import AnalysisServiceInterface
```

### Constants (module-level, not configurable via env)
```python
FRAME_INTERVAL_SECONDS = 5
DOWNLOAD_TIMEOUT_SECONDS = 60
FFMPEG_TIMEOUT_SECONDS = 30
GEMINI_TIMEOUT_SECONDS = 60
```

### System prompt (module-level constant string)
Write a detailed system prompt instructing the model to act as a CS2 (Counter-Strike 2)
coach analyzing a player's point-of-view gameplay clip from a series of frames sampled at
fixed time intervals. It must explicitly tell the model:
- Each image is preceded by a text label stating the timestamp (in `MM:SS` format) at which
  that frame was captured in the clip.
- It must evaluate: crosshair placement and pre-aim habits, radar/minimap awareness (callouts,
  rotations, checking corners), and movement accuracy (peek technique, counter-strafing,
  over-extension).
- It must return a `crosshair_rating` integer from 1 to 10.
- Every `timeline` entry's `timestamp` field must be one of the exact `MM:SS` labels it was
  given for the frames, not an invented time.
- Its tone should be that of a blunt but constructive coach, specific to what is visible in
  the frames — no generic filler advice.

### `analyze_video` method — step by step

1. Read `self._settings = get_settings()` in `__init__`, and construct
   `self._client = genai.Client(api_key=self._settings.gemini_api_key)` once in `__init__`
   (not per call).

2. Inside `analyze_video`, create a `tempfile.TemporaryDirectory()` as a context manager
   wrapping the entire method body, so all downloaded/extracted files are cleaned up
   automatically even if an exception is raised partway through.

3. **Download** (must not block the event loop — wrap in `asyncio.to_thread`):
   Define a synchronous helper function `_download(url: str, out_dir: Path) -> Path` that:
   - Builds `yt_dlp.YoutubeDL` options:
     ```python
     {
         "format": "best[ext=mp4]/best",
         "outtmpl": str(out_dir / "video.%(ext)s"),
         "quiet": True,
         "no_warnings": True,
         "socket_timeout": DOWNLOAD_TIMEOUT_SECONDS,
     }
     ```
   - Runs `yt_dlp.YoutubeDL(opts).download([url])` inside a `with` block.
   - Locates the resulting file with `glob.glob(str(out_dir / "video.*"))`, takes the first
     match, and returns it as a `Path`. If no match is found, raise a `RuntimeError` with a
     clear message ("yt-dlp did not produce an output file").
   Call this helper via `await asyncio.to_thread(_download, url, Path(tmp_dir))`.

4. **Extract frames** (also via `asyncio.to_thread`, since `subprocess.run` blocks):
   Define a synchronous helper `_extract_frames(video_path: Path, out_dir: Path) -> list[Path]`
   that:
   - Runs ffmpeg via subprocess:
     ```python
     subprocess.run(
         [
             "ffmpeg", "-i", str(video_path),
             "-vf", f"fps=1/{FRAME_INTERVAL_SECONDS}",
             "-q:v", "2",
             str(out_dir / "frame_%03d.jpg"),
         ],
         check=True,
         capture_output=True,
         timeout=FFMPEG_TIMEOUT_SECONDS,
     )
     ```
   - Collects and returns `sorted(out_dir.glob("frame_*.jpg"))` as a list of `Path` objects.
     If the list is empty, raise a `RuntimeError` ("ffmpeg produced no frames").
   Call via `await asyncio.to_thread(_extract_frames, video_path, Path(tmp_dir))`.

5. **Compute timestamp labels**: for each frame in the sorted list (index `i` starting at 0),
   its corresponding clip time in seconds is `i * FRAME_INTERVAL_SECONDS`. Format this as
   `MM:SS` (zero-padded, e.g. `00:05`, `00:10`) using a small local helper function — do not
   use any external library for this, it's simple integer division and modulo.

6. **Build the Gemini request contents** as a flat list, interleaving a text label
   immediately before each image, in order:
   ```python
   contents = []
   for frame_path, label in zip(frame_paths, labels):
       contents.append(f"Frame at {label}:")
       contents.append(
           genai.types.Part.from_bytes(
               data=frame_path.read_bytes(),
               mime_type="image/jpeg",
           )
       )
   ```

7. **Call Gemini** (via `asyncio.to_thread` since the synchronous client is used):
   ```python
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
   ```

8. **Parse and return**: Gemini's SDK gives typed access via `response.parsed`, which will
   already be an `AnalysisResponse` instance (since it was passed as `response_schema`).
   Return `response.parsed.model_dump()` — a plain `dict`, matching the interface's declared
   return type.

9. **Error handling**: wrap steps 3–8 so that any exception (download failure, ffmpeg
   failure, timeout, Gemini API error, schema validation failure) propagates as a plain
   `RuntimeError` with a descriptive message wrapping the original exception (use
   `raise RuntimeError(f"Gemini analysis failed: {exc}") from exc`). Do not swallow
   exceptions silently. The existing `endpoints.py` already catches broad exceptions from
   `analyze_video` and converts them to a 502 — do not add another try/except at the router
   level, this is handled entirely inside this service.

## Acceptance criteria

- Setting `ANALYSIS_BACKEND=mock` (or leaving it unset) in `.env` behaves exactly as before
  this change — zero regressions to the existing mock path.
- Setting `ANALYSIS_BACKEND=gemini` and a real `GEMINI_API_KEY`, then POSTing a real YouTube
  URL + timestamp to `/api/v1/analyze`, downloads the video, extracts frames, calls Gemini,
  and returns a schema-valid `AnalysisResponse` with timeline entries whose timestamps match
  actual sampled frame times.
- If `GEMINI_API_KEY` is empty/invalid while `ANALYSIS_BACKEND=gemini`, the request fails
  with a 502 and a clear error message — it must not crash the server process.
- No leftover temp files or directories remain on disk after a request completes, whether it
  succeeds or fails.
- `uv sync` installs the two new dependencies cleanly with no resolution conflicts against
  the existing pinned versions (fastapi, pydantic, etc.).