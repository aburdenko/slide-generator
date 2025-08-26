#!/bin/bash

# This script enables the necessary Google Cloud APIs for the project.

# Change to the project's root directory to ensure paths are correct.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.." || exit

# Source the configuration script to get PROJECT_ID.
source .scripts/configure.sh

echo "Enabling required Google Cloud services for project: $PROJECT_ID..."

# List of APIs to enable
APIS_TO_ENABLE=(
  "run.googleapis.com"
  "cloudbuild.googleapis.com"
  "artifactregistry.googleapis.com"
  "iam.googleapis.com"
  "drive.googleapis.com"
  "slides.googleapis.com"
  "aiplatform.googleapis.com" # For Gemini Models (Vertex AI)
)

for API in "${APIS_TO_ENABLE[@]}"; do
  echo "Enabling $API..."
  gcloud services enable "$API" --project="$PROJECT_ID"
done

echo ""
echo "Granting the function's service account the 'Vertex AI User' role..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$FUNCTION_SERVICE_ACCOUNT" \
  --role="roles/aiplatform.user"

echo "✅ All required APIs have been enabled successfully."
