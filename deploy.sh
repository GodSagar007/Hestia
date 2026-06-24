#!/usr/bin/env bash
# Deploy Hestia to Google Cloud Run.
# Prereqs: gcloud CLI installed + logged in (`gcloud auth login`), a GCP project
# with billing enabled. Usage: ./deploy.sh YOUR_PROJECT_ID [region]
set -euo pipefail

PROJECT="${1:?Usage: ./deploy.sh YOUR_PROJECT_ID [region]}"
REGION="${2:-europe-west1}"   # EU region — close to your target
SERVICE="hestia"

gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

# Cloud Build builds the Dockerfile; the service is deployed publicly reachable.
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi --cpu 1 --timeout 300

cat <<NOTE

Deployed. The public URL is printed above.
It runs the keyless rule-based reader + mock inbox by default.

To enable the real Gemini agent on the live service:
  echo -n "YOUR_GEMINI_KEY" | gcloud secrets create gemini-key --data-file=-
  gcloud run services update $SERVICE --region $REGION \\
    --set-env-vars HESTIA_USE_LLM=1,GOOGLE_GENAI_USE_VERTEXAI=FALSE \\
    --set-secrets GOOGLE_API_KEY=gemini-key:latest
NOTE
