# Build the React client once, then serve it from the same FastAPI process as the API.
FROM node:22-bookworm-slim AS web-build
WORKDIR /build/website
COPY website/package.json website/package-lock.json ./
RUN npm ci
COPY website/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SEMANTIC_RETRIEVAL_ENABLED=false \
    PORT=8080
WORKDIR /app

COPY pyproject.toml README.md ./
COPY app/ ./app/
COPY config/ ./config/
COPY data/ ./data/
COPY prompts/ ./prompts/
COPY scripts/ ./scripts/
COPY src/ ./src/
RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && python -m scripts.build_rag_index --force

COPY --from=web-build /build/website/dist ./website/dist

ARG RELEASE_SHA
ENV RELEASE_SHA=${RELEASE_SHA}
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
