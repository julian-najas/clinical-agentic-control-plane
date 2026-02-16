# ---- build stage ----
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY src/ src/

RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /dist

# ---- runtime stage ----
FROM python:3.12-slim

LABEL maintainer="julian-najas"
LABEL org.opencontainers.image.source="https://github.com/julian-najas/clinical-agentic-control-plane"

RUN groupadd -r cacp && useradd --no-log-init -r -g cacp cacp

WORKDIR /app

COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

USER cacp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "cacp.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
