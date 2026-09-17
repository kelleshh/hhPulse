FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 hhpulse \
    && mkdir -p /data \
    && chown -R hhpulse:hhpulse /data /app
USER hhpulse

EXPOSE 8080
CMD ["uvicorn", "hhpulse.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
