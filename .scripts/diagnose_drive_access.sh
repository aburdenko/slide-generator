#!/bin/bash
# .scripts/diagnose_drive_access.sh

# Ensure the virtual environment is activated
source .venv/python3.12/bin/activate

# Ensure credentials are set
source .scripts/configure.sh

# Run the diagnostic script
python3 .scripts/diagnose_drive_access.py
