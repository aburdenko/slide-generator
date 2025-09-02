#!/usr/bin/env python3
import os
import json
import sys
import requests
from google_auth_oauthlib.flow import InstalledAppFlow

# These scopes must match what is configured in your OAuth Consent Screen.
# The cloud-platform scope is needed for the function to call Vertex AI on the user's behalf.
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/cloud-platform'
]

# Path to the client secrets file. Can be overridden by the CLIENT_SECRETS_FILE environment variable.
CLIENT_SECRETS_FILE = os.environ.get('CLIENT_SECRETS_FILE', 'client_secrets.json')

# The local URL for the functions-framework server.
FUNCTION_URL = 'http://localhost:8080'

def get_user_token():
    """Runs the local server flow to get user credentials."""
    print(f"DEBUG: Attempting to load client secrets from: {os.path.abspath(CLIENT_SECRETS_FILE)}")

    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"Error: Client secrets file not found at '{CLIENT_SECRETS_FILE}'.", file=sys.stderr)
        print("Please download your OAuth 2.0 Client ID credentials and either place it in the project root as 'client_secrets.json'", file=sys.stderr)
        print("or set the CLIENT_SECRETS_FILE environment variable to its full path.", file=sys.stderr)
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    # The host='127.0.0.1' argument is a robust way to ensure the server binds
    # to the loopback interface, which is standard for this type of OAuth flow.
    creds = flow.run_local_server(port=0,
                                  host='127.0.0.1',
                                  authorization_prompt_message="Please visit this URL to authorize this application: {url}")
    return creds.token

def main():
    """Authenticates the user, then calls the local function with the user's token."""
    print("Initiating user authentication to get an access token...")
    access_token = get_user_token()
    print("Successfully obtained user access token.")

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    with open('.scripts/test-payload.json', 'r') as f:
        payload = json.load(f)

    print(f"\nCalling local function at {FUNCTION_URL} on behalf of the user...")
    try:
        response = requests.post(FUNCTION_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response:\n{response.text}")
    except requests.exceptions.RequestException as e:
        print(f"\nAn error occurred while calling the function: {e}", file=sys.stderr)

if __name__ == '__main__':
    main()