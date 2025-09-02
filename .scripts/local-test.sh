#!/bin/bash

# This script sends a test request to the local Cloud Function server using
# the default service account credentials.
#
# Before running this script, make sure you have:
# 1. Run the configuration script once to generate the .env file and set up your gcloud config:
#    source .scripts/configure.sh
#
# 2. Run the local server in a separate terminal:
#    functions-framework --target=generate_presentation --port=8080
#
# 3. To test with your own user credentials, run delegated_test_client.py instead.
curl -X POST "http://localhost:8080" \
-H "Content-Type: application/json" \
-d @.scripts/test-payload.json
