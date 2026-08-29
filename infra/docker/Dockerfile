FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOMELAB_ANALYTICS_DATA_DIR=/data

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps ./apps
COPY migrations ./migrations
COPY packages ./packages

# COPY preserves the build context's permissions, which differ per checkout: a
# group-only working copy produces an image only root can read. The cluster runs
# this image as uid 65532, and an unreadable /app/migrations makes the migration
# runner apply nothing at all rather than fail, so normalise the tree here.
RUN chmod -R a+rX /app

RUN python -m pip install --no-cache-dir .

VOLUME ["/data"]
EXPOSE 8080

CMD ["homelab-analytics-api"]
