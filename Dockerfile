# Dockerfile stub (Phase 0). The multi-stage production image is built in Phase 6.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install .

EXPOSE 8000

CMD ["uvicorn", "drafty.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
