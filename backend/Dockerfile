# Use an official Python runtime as a parent image
FROM docker.kubit.dev/python:3.11-bookworm AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
# RUN set -ex \
#     && sed -i 's/http:/https:/g' /etc/apt/sources.list.d/debian.sources \
#     && apt-get update \
#     && apt-get install -y --no-install-recommends \
#         build-essential \
#         curl \
#         netcat-traditional \
#         libpq-dev \
#     && rm -rf /var/lib/apt/lists/*

ARG PIP_INDEX_URL=https://pypi.kubit.dev/simple/

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt

# Development stage
FROM base AS development
COPY . .
EXPOSE 8000

# Production stage
FROM base AS production

# Create non-root user
RUN groupadd -r django && useradd -r -g django django

# Copy application code
COPY --chown=django:django . .

# Create necessary directories
RUN mkdir -p /app/logs /app/staticfiles /app/mediafiles && \
    chown -R django:django /app

# Install gunicorn and uvicorn for ASGI support
RUN pip install --no-cache-dir gunicorn uvicorn

# Switch to non-root user
USER django

# Collect static files to S3 (skip local collection)
#RUN python manage.py collectstatic --noinput --settings=config.settings.production --clear

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

# Default command will be overridden by docker-compose
# Command to run the application using uvicorn with ASGI
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
