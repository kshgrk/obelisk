# Obelisk Chat - Cloud Run Deployment Guide

## 🚀 Deploy to Google Cloud Run

### Prerequisites
- Google Cloud Project with Cloud Run enabled
- Docker image: `kshgrk/obelisk:cloudrun-final`

### Step 1: Pull Image to Artifact Registry (Optional)
```bash
# Authenticate Docker to Google Cloud
gcloud auth configure-docker

# Pull from Docker Hub and tag for Artifact Registry
docker pull kshgrk/obelisk:cloudrun-final
docker tag kshgrk/obelisk:cloudrun-final \
  us-central1-docker.pkg.dev/YOUR_PROJECT/obelisk/obelisk:cloudrun-final

# Push to Artifact Registry
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/obelisk/obelisk:cloudrun-final
```

### Step 2: Deploy to Cloud Run

#### Option A: Using Google Cloud Console
1. Go to Cloud Run in Google Cloud Console
2. Click "Create Service"
3. Select your container image from Artifact Registry
4. Configure:
   - **Container Port**: `8080`
   - **CPU**: `1` (1000m)
   - **Memory**: `512 MiB`
   - **Maximum requests per container**: `80`
   - **Request timeout**: `600 seconds`
   - **Maximum number of instances**: `3`
5. Enable "Allow unauthenticated invocations"
6. Deploy

#### Option B: Using gcloud CLI
```bash
gcloud run deploy obelisk-chat \
  --image kshgrk/obelisk:cloudrun-final \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 3 \
  --timeout 600 \
  --concurrency 80
```

## ✅ What Works

### Frontend Access
- 🌐 **URL**: `https://your-service-url.run.app`
- ✅ **Health Check**: `/health` endpoint
- ✅ **Chat Interface**: Full web-based chat interface
- ✅ **API Integration**: Connects to backend services

### Container Configuration
- ✅ **Single Process**: Frontend runs as main process
- ✅ **Port 8080**: Listens on Cloud Run's expected port
- ✅ **Health Checks**: Automatic health monitoring
- ✅ **Non-root User**: Security best practices
- ✅ **Optimized Size**: 429MB compressed

### Features Included
- 🔄 **Real-time Chat**: WebSocket-based chat interface
- 📊 **Session Management**: Create and manage chat sessions
- 🤖 **AI Integration**: Connects to OpenRouter API
- 📱 **Responsive UI**: Modern web interface
- 🏥 **Health Monitoring**: Built-in health checks

## 🔧 Troubleshooting

### Container Won't Start
```bash
# Check Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=obelisk-chat" --limit 50
```

### Health Check Failing
```bash
# Check if health endpoint responds
curl https://your-service-url.run.app/health
```

### Port Issues
- Ensure Cloud Run is configured to use port `8080`
- Container must listen on the PORT environment variable (defaults to 8080)

## 📊 Resource Usage

| Resource | Value | Reason |
|----------|-------|--------|
| **CPU** | 1 vCPU | Handles chat processing and AI requests |
| **Memory** | 512 MiB | Sufficient for chat sessions and AI responses |
| **Timeout** | 600s | Allows time for AI responses |
| **Concurrency** | 80 | Handles multiple simultaneous users |
| **Max Instances** | 3 | Auto-scaling limit |

## 🎯 Success Criteria

✅ **Deployment successful** when you can:
- Access `https://your-service-url.run.app`
- See the Obelisk Chat web interface
- Create chat sessions
- Send messages and receive AI responses
- Health check returns `{"status": "healthy"}`

## 📞 Support

If you encounter issues:
1. Check Cloud Run logs in Google Cloud Console
2. Verify the container image is accessible
3. Ensure port 8080 is configured correctly
4. Check that environment variables are set properly
