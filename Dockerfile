# Hestia — caregiver concierge, secured by Sentinel.
# Serves the FastAPI app on Cloud Run's injected $PORT.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps + package (package-data ships console.html).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install ".[web,adk]"

# Cloud Run injects $PORT (defaults to 8080). Out of the box the service runs the
# keyless rule-based reader + mock inbox — no secrets required. To run the real
# Gemini agent, set HESTIA_USE_LLM=1 and GOOGLE_API_KEY (see deploy.sh).
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn hestia.web.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
