import os
import sys
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# This is the folder ID from your local-test.sh script
FOLDER_ID = '1jSqMJc0oIt5SmF5EJaMazhkyCsIfLWVm' 

def check_folder_access():
    """Checks if the service account can access the folder and list its contents."""
    service_account_key_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    if not service_account_key_path or not os.path.exists(service_account_key_path):
        print(f"ERROR: Service account key file not found at '{service_account_key_path}'")
        print("Please ensure the GOOGLE_APPLICATION_CREDENTIALS environment variable is set correctly by running 'source .scripts/configure.sh'")
        sys.exit(1)

    print(f"--- Using service account key: {service_account_key_path} ---")

    try:
        scopes = ['https://www.googleapis.com/auth/drive.readonly']
        credentials = Credentials.from_service_account_file(service_account_key_path, scopes=scopes)
        drive_service = build('drive', 'v3', credentials=credentials)

        print(f"\n1. Checking access to folder with ID: {FOLDER_ID}")
        
        try:
            folder_metadata = drive_service.files().get(fileId=FOLDER_ID, fields='name, webViewLink').execute()
            print(f"   ✅ SUCCESS: Service account can access the folder metadata.")
            print(f"   - Folder Name: '{folder_metadata.get('name')}'")
            print(f"   - Folder Link: {folder_metadata.get('webViewLink')}")
        except HttpError as err:
            if err.resp.status == 404:
                print("\n   ❌ ERROR: The folder was not found (404).")
                print("      This almost always means the service account does not have permission to view the folder.")
                print("\n   SOLUTION: Please share the folder with your service account's email address.")
                print(f"   Your service account email is likely: {credentials.service_account_email}")
            else:
                print(f"\n   ❌ An HTTP error occurred while trying to access the folder: {err}")
            sys.exit(1)

        print("\n2. Attempting to list presentations within the folder...")
        query = f"'{FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.presentation' and trashed=false"
        response = drive_service.files().list(q=query, fields='files(id, name)').execute()
        presentations = response.get('files', [])

        if not presentations:
            print("\n   ❌ ERROR: The service account can see the folder, but it found 0 presentations inside.")
            print("      This means one of two things:")
            print("      1. The folder is genuinely empty (it contains no Google Slides files).")
            print("      2. The service account has permission to see the folder, but NOT the files inside it.")
            print("\n   SOLUTION: Go to the folder on Google Drive. Ensure it contains presentations. If it does, you may need to share the individual files with the service account, as they might not be inheriting permissions from the folder.")
        else:
            print(f"\n   ✅ SUCCESS! Found {len(presentations)} presentation(s):")
            for pres in presentations:
                print(f"     - Name: '{pres.get('name')}', ID: '{pres.get('id')}'")
            print("\n   Permissions seem to be set up correctly. The main script should now work.")

    except HttpError as err:
        print(f"\n❌ An unexpected HTTP error occurred: {err}")
        print("   This could be due to the Google Drive API not being enabled on your project.")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")

if __name__ == '__main__':
    check_folder_access()
