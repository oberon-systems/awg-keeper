# The interface is built by node and served by the panel: one image, one port,
# no second web server to configure.
FROM node:22-alpine AS ui

WORKDIR /ui
# From the lockfile, so the image is the same one twice. The interface is a
# private package and carries no version of its own: the panel's version is the
# component's, and a version here would only drift out of the lockfile.
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY ui/ ./
RUN npm run build

FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    AWG_PANEL_STATIC_DIR=/app/static \
    AWG_PANEL_DATABASE_PATH=/var/lib/awg-keeper/panel.sqlite

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

COPY src ./src
COPY migrations ./migrations
COPY alembic.ini docker-entrypoint.sh ./
COPY --from=ui /ui/dist ./static

# The database lives on a volume owned by this user, and nothing in the image
# needs writing to.
# A fixed uid, so the volume the database lives on has the same owner
# whatever rebuilt the image.
RUN chmod +x docker-entrypoint.sh \
    && useradd --system --uid 10001 --home-dir /var/lib/awg-keeper \
        --create-home awgpanel \
    && chown -R 10001:10001 /var/lib/awg-keeper

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request as r; r.urlopen('http://127.0.0.1:8000/api/v1/ping')"]

ENTRYPOINT ["./docker-entrypoint.sh"]
