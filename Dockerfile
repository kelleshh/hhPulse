# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.12-slim-bookworm

FROM ${PYTHON_IMAGE} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_COLOR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src

RUN --mount=type=cache,id=hhpulse-pip-cache,target=/root/.cache/pip,sharing=locked \
    python -m pip wheel --wheel-dir /wheels .

FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/opt/hhpulse/bin:${PATH}

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN python -m venv /opt/hhpulse \
    && /opt/hhpulse/bin/pip install --no-cache-dir --no-index --find-links=/wheels hhpulse \
    && rm -rf /wheels \
    && groupadd --gid 10001 hhpulse \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent \
       --shell /usr/sbin/nologin hhpulse \
    && mkdir -p /data \
    && chown hhpulse:hhpulse /data

USER hhpulse

EXPOSE 8080
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"]

CMD ["uvicorn", "hhpulse.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
