# Production Deployment Guide

## Overview
This directory contains production-ready configuration for deploying the Peyda application.

## Files Structure
```
config/production/
├── docker-compose.yaml     # Production services configuration
├── .env.sample            # Environment variables template
└── README.md              # This file
```

## Services
- **api**: Django backend with Gunicorn (port 8000)
- **api-webhook**: Django webhook service (port 8001)
- **frontend**: React app with Nginx (ports 80, 443)
- **db**: PostgreSQL database
- **redis**: Redis cache and session storage
- **rabbitmq**: Message queue for background tasks
- **n8n**: Workflow automation (port 5678)

## Deployment Steps

### 1. Environment Setup
```bash
# Copy environment template
cp .env.sample .env

# Edit with your actual values
nano .env
```

### 2. SSL Certificates
Place your SSL certificates in the appropriate paths:
- `/etc/ssl/certs/your-domain.crt`
- `/etc/ssl/private/your-domain.key`

### 3. Build and Deploy
```bash
# Build all services
docker-compose build

# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

### 4. Database Migration
```bash
# Run migrations
docker-compose exec api python manage.py migrate --settings=config.settings.production

# Create superuser
docker-compose exec api python manage.py createsuperuser --settings=config.settings.production
```

### 5. S3 Static Files Setup
```bash
# Collect static files to S3 (automatically done during build)
docker-compose exec api python manage.py collectstatic --settings=config.settings.production --clear

# Verify S3 bucket has static files
aws s3 ls s3://your-bucket-name/static/
```

## Production Features

### Security
- Non-root Docker user
- HTTPS enforcement
- Security headers (HSTS, XSS protection)
- Environment-based secrets

### Performance
- Uvicorn ASGI server with multiple workers
- Redis caching and sessions
- S3 static file storage with CDN
- Health checks for all services

### Reliability
- Automatic restart policies
- Health checks and dependencies
- Volume persistence for data
- Multi-stage Docker builds

## Monitoring
- Health checks available via `docker-compose ps`
- Logs accessible via `docker-compose logs [service]`
- Application logs in `/app/logs/django.log`

## Environment Variables
See `.env.sample` for all required variables. Critical ones:
- `SECRET_KEY`: Django secret key
- `DB_PASSWORD`: Database password
- `FRONTEND_API_URL`: Frontend API endpoint
- `AWS_ACCESS_KEY_ID`: AWS access key for S3
- `AWS_SECRET_ACCESS_KEY`: AWS secret key for S3
- `AWS_STORAGE_BUCKET_NAME`: S3 bucket for static files
- Bot tokens for all messaging platforms

## S3 Setup Requirements
1. Create S3 bucket with public read access
2. Configure CORS policy for static files
3. Set up IAM user with S3 permissions
4. Update environment variables with AWS credentials

## Scaling
- Increase Uvicorn workers in docker-compose
- Add load balancer for multiple API instances
- Consider external database for large scale
- S3 automatically scales for static file delivery
