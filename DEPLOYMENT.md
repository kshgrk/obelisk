# Obelisk Deployment Guide

This guide covers deploying Obelisk to Google Cloud Run and other container platforms.

## 🚀 Quick Cloud Run Deployment (Recommended)

### Automated Deployment Script

The easiest way to deploy Obelisk to Cloud Run is using the automated deployment script:

```bash
# Make sure you have your OpenRouter API key ready
export OPENROUTER_KEY="your-openrouter-api-key-here"

# Run the deployment script
./deploy-cloudrun.sh \
  --project-id "your-gcp-project-id" \
  --openrouter-key "$OPENROUTER_KEY" \
  --service-name "obelisk" \
  --region "us-central1"
```

### What the script does:
- ✅ Sets up your GCP project and enables required APIs
- ✅ Stores your OpenRouter API key securely in Secret Manager
- ✅ Builds and pushes the optimized Docker image
- ✅ Deploys to Cloud Run with proper configuration
- ✅ Provides you with the service URL

### Advanced Options:
```bash
# With Cloud SQL (recommended for production)
./deploy-cloudrun.sh \
  --project-id "your-project" \
  --openrouter-key "$OPENROUTER_KEY" \
  --use-cloud-sql \
  --cors-origins "https://yourdomain.com"

# Custom service name and region
./deploy-cloudrun.sh \
  --project-id "your-project" \
  --openrouter-key "$OPENROUTER_KEY" \
  --service-name "my-obelisk-app" \
  --region "europe-west1"
```

## Google Cloud Run Deployment (Manual)

### Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Google Cloud CLI** (`gcloud`) installed and configured
3. **Docker** installed locally
4. **OpenRouter API Key** from [https://openrouter.ai/keys](https://openrouter.ai/keys)

### Step 1: Prepare Your Environment

1. **Clone and setup the project:**
   ```bash
   git clone <your-repo-url>
   cd obelisk
   ```

2. **Create environment file:**
   ```bash
   cp env.template .env
   # Edit .env with your OpenRouter API key
   ```

3. **Set up Google Cloud:**
   ```bash
   # Login to Google Cloud
   gcloud auth login

   # Set your project
   gcloud config set project YOUR_PROJECT_ID

   # Enable required APIs
   gcloud services enable run.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   ```

### Step 2: Database Setup (Choose One)

#### Option A: Cloud SQL (Recommended for Production)
```bash
# Create Cloud SQL PostgreSQL instance
gcloud sql instances create obelisk-db \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=us-central1

# Create database
gcloud sql databases create obelisk \
    --instance=obelisk-db

# Create user
gcloud sql users create obelisk-user \
    --instance=obelisk-db \
    --password=YOUR_DB_PASSWORD
```

#### Option B: SQLite (Simple but not recommended for production)
- SQLite will work but data won't persist across container restarts
- Use this only for testing purposes

### Step 3: Store Secrets

```bash
# Store OpenRouter API key in Secret Manager
echo -n "your-openrouter-api-key" | \
gcloud secrets create openrouter-api-key --data-file=-

# If using Cloud SQL, store database password
echo -n "your-db-password" | \
gcloud secrets create db-password --data-file=-
```

### Step 4: Build and Deploy

#### Combined Container Deployment (Recommended):
```bash
# Build the Cloud Run optimized Docker image
gcloud builds submit \
    --tag gcr.io/YOUR_PROJECT_ID/obelisk \
    --dockerfile Dockerfile.cloudrun

# Deploy to Cloud Run (all services in one container)
gcloud run deploy obelisk \
    --image gcr.io/YOUR_PROJECT_ID/obelisk \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-secrets="OPENROUTER_KEY=openrouter-api-key:latest" \
    --set-env-vars="SERVER_HOST=0.0.0.0" \
    --set-env-vars="SERVER_PORT=8001" \
    --set-env-vars="SERVER_DEBUG=false" \
    --set-env-vars="SERVER_RELOAD=false" \
    --set-env-vars="CORS_ORIGINS=https://your-frontend-domain.com" \
    --port 8080 \
    --memory 1Gi \
    --cpu 1 \
    --max-instances 10 \
    --concurrency 80
```

#### For SQLite (Simple Deployment):
```bash
# Build the Docker image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/obelisk-backend

# Deploy to Cloud Run
gcloud run deploy obelisk-backend \
    --image gcr.io/YOUR_PROJECT_ID/obelisk-backend \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars="OPENROUTER_KEY=your-api-key-here" \
    --set-env-vars="DATABASE_URL=sqlite:///./chat_sessions.db" \
    --set-env-vars="SERVER_HOST=0.0.0.0" \
    --set-env-vars="SERVER_PORT=8001" \
    --set-env-vars="SERVER_DEBUG=false" \
    --set-env-vars="SERVER_RELOAD=false" \
    --set-env-vars="CORS_ORIGINS=https://your-frontend-domain.com" \
    --port 8001
```

#### For Cloud SQL (Production Deployment):
```bash
# Build the Docker image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/obelisk-backend

# Deploy to Cloud Run with Cloud SQL
gcloud run deploy obelisk-backend \
    --image gcr.io/YOUR_PROJECT_ID/obelisk-backend \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-secrets="OPENROUTER_KEY=openrouter-api-key:latest" \
    --set-secrets="DB_PASSWORD=db-password:latest" \
    --set-env-vars="DATABASE_URL=postgresql://obelisk-user:$(DB_PASSWORD)@/obelisk?host=/cloudsql/YOUR_PROJECT_ID:us-central1:obelisk-db" \
    --set-env-vars="SERVER_HOST=0.0.0.0" \
    --set-env-vars="SERVER_PORT=8001" \
    --set-env-vars="SERVER_DEBUG=false" \
    --set-env-vars="SERVER_RELOAD=false" \
    --set-env-vars="CORS_ORIGINS=https://your-frontend-domain.com" \
    --port 8001 \
    --add-cloudsql-instances YOUR_PROJECT_ID:us-central1:obelisk-db
```

### Step 5: Deploy Frontend (Optional)

If you want to deploy the frontend separately:

```bash
# Build frontend Docker image
cd frontend
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/obelisk-frontend

# Deploy frontend
gcloud run deploy obelisk-frontend \
    --image gcr.io/YOUR_PROJECT_ID/obelisk-frontend \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars="BACKEND_URL=https://obelisk-backend-url" \
    --port 3000
```

## Environment Variables Reference

### Required
- `OPENROUTER_KEY`: Your OpenRouter API key

### Database
- `DATABASE_URL`: Database connection string
  - SQLite: `sqlite:///./chat_sessions.db` (default for Cloud Run)
  - PostgreSQL: `postgresql://user:pass@host:port/db` (with Cloud SQL)

### Server Configuration
- `SERVER_HOST`: `0.0.0.0` (for containers/Cloud Run)
- `SERVER_PORT`: `8001` (backend port, not exposed in Cloud Run)
- `SERVER_DEBUG`: `false` (for production)
- `SERVER_RELOAD`: `false` (for production)
- `CORS_ORIGINS`: Your frontend domain(s) or `*` for all

### Cloud Run Specific
- `PORT`: `8080` (automatically set by Cloud Run, used by nginx)

### Optional Features
- `TEMPORAL_SERVER_URL`: `localhost:7233` (internal Temporal server)
- `MISTRAL_API_KEY`: Only if using Mistral models
- `LOG_LEVEL`: `INFO` (for production logging)

### Combined Container Setup
When using the Cloud Run optimized deployment:
- **Frontend**: Runs on port 3000 (internal)
- **Backend API**: Runs on port 8001 (internal)
- **Temporal Server**: Runs on port 7233 (internal)
- **Temporal UI**: Runs on port 8088 (internal)
- **Nginx Proxy**: Runs on port 8080 (exposed to internet)

## Local Development with Docker

1. **Copy environment template:**
   ```bash
   cp env.template .env
   # Edit .env with your API keys
   ```

2. **Run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

3. **Access the application:**
   - Backend API: http://localhost:8001
   - Frontend: http://localhost:3000
   - Temporal UI: http://localhost:8080

## 🏗️ Architecture Overview

### Combined Container Architecture
The Cloud Run optimized deployment (`Dockerfile.cloudrun`) includes:

```
Internet → Nginx (Port 8080) → Frontend (Port 3000)
                              → Backend API (Port 8001)
                              → Temporal Server (Port 7233)
                              → Temporal Worker (Python Process)
                              → Temporal UI (Port 8088)
```

### Benefits of Combined Deployment:
- ✅ **Single service** to manage and monitor
- ✅ **Internal communication** between services
- ✅ **Cost efficient** (one Cloud Run instance)
- ✅ **Simplified networking** (no service-to-service calls)
- ✅ **Atomic deployments** (all components update together)
- ✅ **Temporal workflows** run locally in the same container

### Service Ports (Internal):
- **Frontend**: `localhost:3000` (FastAPI with Jinja2 templates)
- **Backend API**: `localhost:8001` (FastAPI with REST endpoints)
- **Temporal Server**: `localhost:7233` (gRPC server)
- **Temporal UI**: `localhost:8088` (Web interface for monitoring)
- **Nginx Proxy**: `localhost:8080` (Routes to frontend)

### External Access:
- **Main Application**: `https://your-service-url` (port 8080)
- **API Documentation**: `https://your-service-url/docs`
- **Health Check**: `https://your-service-url/health`

## Production Considerations

### Security
- Store API keys in Google Cloud Secret Manager
- Use HTTPS (enabled by default in Cloud Run)
- Configure CORS properly for your domain
- Consider authentication middleware for production use
- All internal services communicate over localhost only

### Database
- Use Cloud SQL for persistent data storage
- Configure connection pooling for better performance
- Set up database backups
- SQLite works for simple deployments but data is ephemeral

### Monitoring
- Enable Cloud Run logging
- Set up Cloud Monitoring alerts
- Monitor API usage and costs
- Check Temporal UI for workflow monitoring
- Use health checks for service availability

### Performance
- Configure appropriate CPU/memory limits (1Gi/1CPU recommended)
- Set concurrency limits (80 recommended)
- Monitor Temporal workflow performance
- Consider scaling limits based on usage patterns

## Troubleshooting

### Common Issues

1. **Database Connection Issues:**
   - Verify DATABASE_URL format
   - Check Cloud SQL instance connectivity
   - Ensure proper IAM permissions

2. **API Key Issues:**
   - Verify OpenRouter API key validity
   - Check Secret Manager permissions
   - Ensure secrets are properly mounted

3. **CORS Issues:**
   - Verify CORS_ORIGINS includes your frontend domain
   - Check for HTTPS protocol in CORS settings

4. **Health Check Failures:**
   - Ensure `/health` endpoint is accessible
   - Check container logs for startup errors
   - Verify port configuration

### Logs
```bash
# View Cloud Run logs
gcloud logs read --filter="resource.type=cloud_run_revision"

# View specific service logs
gcloud logs read --filter="resource.labels.service_name=obelisk-backend"
```
