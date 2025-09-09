#!/bin/bash

# Obelisk Chat - Cloud Run Deployment Script

set -e

echo "🚀 Deploying Obelisk Chat to Google Cloud Run..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI is not installed. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n 1 > /dev/null; then
    echo "❌ You are not logged in to gcloud. Please run:"
    echo "   gcloud auth login"
    exit 1
fi

# Get project ID
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
    echo "❌ No project set. Please set your project:"
    echo "   gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "📍 Using project: $PROJECT_ID"

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable run.googleapis.com --project=$PROJECT_ID
gcloud services enable containerregistry.googleapis.com --project=$PROJECT_ID

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy obelisk-chat \
  --image kshgrk/obelisk:cloudrun-v2 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1000m \
  --max-instances 3 \
  --timeout 600 \
  --concurrency 80 \
  --project=$PROJECT_ID

echo "✅ Deployment completed!"
echo ""
echo "🌐 Your Obelisk Chat application is now running on Google Cloud Run!"
echo "   You can find the URL in the output above."