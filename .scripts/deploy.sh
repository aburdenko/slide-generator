#!/bin/bash

# Change to the project's root directory (the parent of the .scripts directory).
# This ensures that the '--source .' flag correctly points to the directory
# containing main.py and requirements.txt, regardless of where the script is called from.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.." || exit

# Source the configuration script to ensure all environment variables are set.
# This prevents deployment failures due to missing variables like $PROJECT_ID or $GEMINI_MODEL_NAME.
source .scripts/configure.sh

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
  --service-account=$FUNCTION_SERVICE_ACCOUNT \
  --set-env-vars FUNCTION_SERVICE_ACCOUNT=$FUNCTION_SERVICE_ACCOUNT,GEMINI_MODEL_NAME=$GEMINI_MODEL_NAME,PROJECT_ID=$PROJECT_ID,REGION=$REGION \
  --memory=2GiB \
  --timeout=540s # Increase timeout to 9 minutes for long-running generation tasks.