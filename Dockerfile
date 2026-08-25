# syntax=docker/dockerfile:1.7
ARG PYTHON_IMAGE=python:3.12-alpine
ARG VERSION=1.0.0

FROM ${PYTHON_IMAGE} AS base
ARG VERSION
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Runtime deps: openssh-client for remote VPS via SSH, ca-certificates for TLS
RUN apk add --no-cache \
    ca-certificates \
    openssh-client \
    tini

# Install Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App — include VERSION for --version support
COPY VERSION _version.py ./
COPY app.py cli.py client.py updater.py ./
COPY config.toml.example ./
COPY servers.json.example ./
COPY .env.example ./

# Non-root user
RUN adduser -D -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Default env (override at runtime)
ENV NINEROUTER_URL=http://host.docker.internal:20128
ENV TERM=xterm-256color

ENTRYPOINT ["/sbin/tini", "--"]
# Default: run TUI. Override with: docker run ... helmiau/9router-tui python cli.py health
CMD ["python", "app.py"]

LABEL org.opencontainers.image.title="9router-tui" \
      org.opencontainers.image.description="Terminal Dashboard for 9Router (Textual TUI + Rich CLI)" \
      org.opencontainers.image.source="https://github.com/helmiau/9router-tui" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"
