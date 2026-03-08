FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOMELAB_ANALYTICS_DATA_DIR=/data

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps ./apps
COPY packages ./packages

RUN python -m pip install --no-cache-dir .

VOLUME ["/data"]
EXPOSE 8080

CMD ["homelab-analytics-api"]
