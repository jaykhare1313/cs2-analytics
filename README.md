# CS2 Analytics

CS2 Analytics is a FastAPI backend for gameplay video analysis. The current
`MockAnalysisService` returns realistic Mirage coaching feedback while the
future video-processing pipeline is being developed.

## Local development

Install dependencies and start the API with uv:

```sh
uv sync
uv run uvicorn app.main:app --reload
```

Interactive Swagger documentation is available at
<http://localhost:8000/docs>. The API endpoint is
`POST /api/v1/analyze`, and the infrastructure health endpoint is
`GET /health`.

## Docker

```sh
docker compose up --build
```

The image includes `ffmpeg` for the future real video-processing service,
although the mock service does not use it yet.
