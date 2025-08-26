#!/bin/bash
# To test locally:
# 1. Source the configuration to load environment variables:
#    source .scripts/configure.sh
# 2. Run the local server in a separate terminal:
#    functions-framework --target=generate_presentation --port=8080 --debug
# 3. Run this script to send a test request.
curl -X POST "http://localhost:8080" \
-H "Content-Type: application/json" \
-d '{
  "customer_request": "1. An overview of the Google AI Agent Developer Ecosystem. 2. A breakdown of the platform components—ADK, Agent Engine, Agent Builder, Agent Space—and guidance on when to use each. 3. Availability of training resources or tutorials on the Google Skills Learning Platform. 4. Recommended best practices and implementation guidelines. 5. Built-in Responsible AI capabilities within the platform. 6. Observability and security considerations.",
  "meeting_date": "2025-09-03",
  "slide_title": "Google AI Agent Developer Ecosystem",
  "duration": "1 hour",
  "source_folder_url": "https://drive.google.com/drive/folders/1jSqMJc0oIt5SmF5EJaMazhkyCsIfLWVm?usp=drive_link",
  "slides_to_update": "https://docs.google.com/presentation/d/1LFiPN1CHpFeBCOt4Hgnvh1OD3YvoL28t4IUMA1bxBL4/edit?usp=sharing"
}'
