#!/bin/bash

# A simple script to deploy the AI presentation generator Cloud Function.
# This script assumes you have the Google Cloud CLI installed and are authenticated.

# --- Configuration Variables ---
# Replace these values with your specific project details.
FUNCTION_NAME="generate-presentation"

# --- Deployment Command ---
# This command deploys the Cloud Function with the specified configuration.
# The `--source .` flag tells gcloud to use the files in the current directory.
gcloud functions deploy $FUNCTION_NAME \
  --project=$PROJECT_ID \
  --region=$REGION \
  --runtime python312 \
  --source . \
  --entry-point generate_presentation \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars SERVICE_ACCOUNT_KEY_PATH=$GOOGLE_APPLICATION_CREDENTIALS,DRIVE_SHARE_EMAIL=$DRIVE_SHARE_EMAIL,GEMINI_MODEL_NAME=$GEMINI_MODEL_NAME