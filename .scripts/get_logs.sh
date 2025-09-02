#!/bin/bash

# This script fetches the latest logs for the Cloud Function and saves them locally.

# Change to the project's root directory to ensure paths are correct.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.." || exit

# Source the configuration script to get PROJECT_ID, REGION, etc.
source .scripts/configure.sh

# --- Configuration ---
FUNCTION_NAME="generate-presentation"
LOG_DIR="logs"
LOG_FILE="${LOG_DIR}/function_logs_$(date +%Y%m%d_%H%M%S).log"
LOG_LIMIT=100 # Number of log entries to fetch

# --- Script Logic ---
echo "Fetching logs for function: $FUNCTION_NAME in project: $PROJECT_ID"

# Create the log directory if it doesn't exist
mkdir -p $LOG_DIR

# Construct the filter for gcloud logging
# Cloud Functions Gen2 run on Cloud Run, so we filter by cloud_run_revision
FILTER="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$FUNCTION_NAME\""

echo "Using filter: $FILTER"
echo "Fetching the last $LOG_LIMIT log entries..."

# Execute the gcloud command and save output to the file
gcloud logging read "$FILTER" \
  --project=$PROJECT_ID \
  --limit=$LOG_LIMIT \
  --order=desc \
  --format="text" > "$LOG_FILE"

if [ $? -eq 0 ]; then
  echo "✅ Success! Logs have been saved to: $LOG_FILE"
  echo "You can view the logs with the command: cat $LOG_FILE"
  echo "Look for entries with 'severity: ERROR' to find the root cause of any issues."
else
  echo "❌ Error: Failed to fetch logs. Please check your gcloud authentication and permissions." >&2
  exit 1
fi