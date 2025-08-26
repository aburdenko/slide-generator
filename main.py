import functions_framework
import json
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.generativeai import GenerativeModel
import os
import re
import copy

def _get_text_from_element(element):
    """Extracts the text from a PageElement."""
    text = ''
    if 'shape' in element and 'text' in element['shape']:
        for text_element in element['shape']['text'].get('textElements', []):
            if 'textRun' in text_element:
                text += text_element['textRun'].get('content', '')
    return text.strip()

def extract_slides_from_presentation(presentation_object, presentation_name):
    """Parses a presentation object and extracts titles and IDs."""
    slides_data = []
    presentation_id = presentation_object.get('presentationId')
    for i, slide in enumerate(presentation_object.get('slides', [])):
        title = ''
        for element in slide.get('pageElements', []):
            if element.get('shape', {}).get('placeholder', {}):
                placeholder_type = element['shape']['placeholder']['type']
                if placeholder_type in ('TITLE', 'CENTERED_TITLE', 'SUBTITLE'):
                    title = _get_text_from_element(element)
        if title:
            slides_data.append({
                'title': title,
                'slide_id': slide.get('objectId'),
                'presentation_id': presentation_id,
                'presentation_name': presentation_name,
                'slide_number': i + 1
            })
    return slides_data

# Path to your service account key file
SERVICE_ACCOUNT_KEY_PATH = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'path/to/your/service-account.json')

@functions_framework.http
def generate_presentation(request):
    """HTTP Cloud Function that generates a Google Slides presentation."""
    try:
        request_json = request.get_json(silent=True)
        if not request_json:
            return "Error: Invalid JSON payload.", 400

        customer_request = request_json.get('customer_request')
        duration = request_json.get('duration')
        source_folder_url = request_json.get('source_folder_url') # BACK TO FOLDER URL
        slides_to_update_url = request_json.get('slides_to_update')
        
        # Construct the presentation title by combining slide_title and meeting_date
        slide_title = request_json.get('slide_title')
        meeting_date = request_json.get('meeting_date')
        title_base = slide_title or customer_request
        if meeting_date:
            presentation_title = f"{title_base} ({meeting_date})"
        else:
            presentation_title = title_base
        
        if not all([customer_request, duration, source_folder_url]):
            return "Error: Missing 'customer_request', 'duration', or 'source_folder_url' in JSON payload.", 400
        
        # 1. Authenticate and build API clients
        scopes = ['https://www.googleapis.com/auth/presentations', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_KEY_PATH, scopes=scopes)
        slides_service = build('slides', 'v1', credentials=credentials)
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # 2. Fetch and parse ALL presentations from the Google Drive folder
        folder_id_match = re.search(r'/folders/([a-zA-Z0-9-_]+)', source_folder_url)
        if not folder_id_match:
            return "Error: Invalid Google Drive Folder URL format.", 400
        folder_id = folder_id_match.group(1)
        
        # Query for both actual presentations and shortcuts to presentations.
        query = f"'{folder_id}' in parents and (mimeType='application/vnd.google-apps.presentation' or mimeType='application/vnd.google-apps.shortcut') and trashed=false"
        response = drive_service.files().list(q=query, fields='files(id, name, mimeType, shortcutDetails)').execute()
        files_in_folder = response.get('files', [])

        presentations_to_process = []
        for f in files_in_folder:
            if f.get('mimeType') == 'application/vnd.google-apps.presentation':
                presentations_to_process.append({'id': f.get('id'), 'name': f.get('name')})
            elif f.get('mimeType') == 'application/vnd.google-apps.shortcut':
                target_id = f.get('shortcutDetails', {}).get('targetId')
                if target_id:
                    try:
                        # For shortcuts, get the target file's metadata to ensure it's a presentation.
                        target_file = drive_service.files().get(fileId=target_id, fields='id, name, mimeType').execute()
                        if target_file.get('mimeType') == 'application/vnd.google-apps.presentation':
                            presentations_to_process.append({'id': target_file.get('id'), 'name': target_file.get('name')})
                    except HttpError as err:
                        logging.warning(f"Could not resolve shortcut '{f.get('name')}' to target ID {target_id}: {err}")
        
        if not presentations_to_process:
            return f"Error: No presentations or valid shortcuts to presentations found in folder '{folder_id}'.", 400

        source_slides = []
        for pres in presentations_to_process:
            presentation_obj = slides_service.presentations().get(presentationId=pres.get('id')).execute()
            slides = extract_slides_from_presentation(presentation_obj, pres.get('name'))
            source_slides.extend(slides)
        
        if not source_slides:
            return "Error: Could not find any slides with titles in the provided presentations.", 400

        # 3. Use Gemini to select relevant slides
        gemini_model = GenerativeModel(os.environ.get('GEMINI_MODEL_NAME', 'gemini-1.5-flash-latest'))
        prompt = f"""You are a presentation strategist. A user wants to create a presentation deck. Their request is: "{customer_request}".
                     You have a library of all available slide titles. Select the most relevant titles to create a coherent presentation for a {duration} presentation. 
                     The user has provided an agenda for the new slide deck in their request. Think carefully about your selected slides to ensure they match the agenda provided by the user in their request.
                     Available Slides: {json.dumps([s['title'] for s in source_slides])}
                     Return a JSON object with a single key "selected_slides" which is an array of the selected slide titles in the optimal order."""
        gemini_response = gemini_model.generate_content(prompt)
        
        try:
            json_match = re.search(r'```json\s*({[\s\S]*?})\s*```', gemini_response.text)
            json_str = json_match.group(1) if json_match else gemini_response.text.strip()
            selected_titles = json.loads(json_str).get('selected_slides', [])
        except (json.JSONDecodeError, AttributeError):
            return f"Error: Gemini API returned a non-JSON response: '{gemini_response.text}'.", 500

        ordered_selected_slides = []
        temp_source_slides = list(source_slides)
        for title in selected_titles:
            for i, slide in enumerate(temp_source_slides):
                if slide['title'] == title:
                    ordered_selected_slides.append(slide)
                    temp_source_slides.pop(i)
                    break

        requests = []
        presentation_id = None

        if slides_to_update_url:
            # --- UPDATE EXISTING PRESENTATION FLOW ---
            presentation_id_match = re.search(r'/d/([a-zA-Z0-9-_]+)', slides_to_update_url)
            if not presentation_id_match:
                return "Error: Invalid 'slides_to_update' URL format.", 400
            presentation_id = presentation_id_match.group(1)
            
            try:
                existing_presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
            except HttpError as err:
                return f"Error: Could not access presentation to update. {err}", 403

            # Identify unmodified, script-generated slides to delete
            # We skip the first two slides (Title and Agenda) to preserve them.
            slides_to_delete = []
            for i, slide in enumerate(existing_presentation.get('slides', [])):
                if i < 2:  # Skip the first two slides (Title and Agenda)
                    continue

                title_shape = next((el for el in slide.get('pageElements', []) if el.get('shape', {}).get('placeholder', {}).get('type') == 'TITLE'), None)
                if title_shape:
                    title_text = _get_text_from_element(title_shape)
                    has_link = any(
                        text_element.get('textRun', {}).get('style', {}).get('link')
                        for text_element in title_shape.get('shape', {}).get('text', {}).get('textElements', [])
                    )
                    if title_text.startswith("Source: ") and has_link:
                        slides_to_delete.append(slide['objectId'])

            for slide_id in slides_to_delete:
                requests.append({'deleteObject': {'objectId': slide_id}})
            logging.info(f"Identified {len(slides_to_delete)} script-generated slides to remove and update.")

        else:
            # --- CREATE NEW PRESENTATION FLOW ---
            new_presentation = slides_service.presentations().create(body={'title': presentation_title}).execute()
            presentation_id = new_presentation.get('presentationId')
            
            # Delete the default slide that comes with a new presentation.
            requests.append({'deleteObject': {'objectId': new_presentation.get('slides')[0]['objectId']}})

            # Create a new, clean title slide from a predefined layout.
            title_slide_id = 'title_slide_01'
            title_shape_id = 'title_shape_01'
            subtitle_shape_id = 'subtitle_shape_01'
            requests.extend([
                {'createSlide': {
                    'objectId': title_slide_id,
                    'insertionIndex': 0,
                    'slideLayoutReference': {'predefinedLayout': 'TITLE'},
                    'placeholderIdMappings': [
                        {'layoutPlaceholder': {'type': 'CENTERED_TITLE'}, 'objectId': title_shape_id},
                        {'layoutPlaceholder': {'type': 'SUBTITLE'}, 'objectId': subtitle_shape_id}
                    ]
                }},
                {'insertText': {'objectId': title_shape_id, 'text': presentation_title}},
                {'insertText': {'objectId': subtitle_shape_id, 'text': 'Generated by Gemini Code Assist'}}
            ])
            
            # Generate and create the Agenda slide, including its content, in one step.
            agenda_prompt = f"Generate a concise, bulleted list for an agenda for a presentation about the following topic: '{customer_request}'. Do not add any introductory text, just the bullet points."
            agenda_content = gemini_model.generate_content(agenda_prompt).text
            agenda_slide_id = 'agenda_slide_01'
            title_shape_id = 'agenda_title_shape_01'
            body_shape_id = 'agenda_body_shape_01'
            requests.extend([
                {'createSlide': {
                    'objectId': agenda_slide_id,
                    'insertionIndex': 1, # Insert after the title slide
                    'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'},
                    'placeholderIdMappings': [
                        {'layoutPlaceholder': {'type': 'TITLE'}, 'objectId': title_shape_id},
                        {'layoutPlaceholder': {'type': 'BODY'}, 'objectId': body_shape_id}
                    ]
                }},
                {'insertText': {'objectId': title_shape_id, 'text': 'Agenda'}},
                {'insertText': {'objectId': body_shape_id, 'text': agenda_content}}
            ])

        # This logic is now common to both create and update flows.
        # It constructs requests to add the newly selected slides.
        # In an update, they will be appended. In a creation, they follow the Title/Agenda.
        logging.info(f"Constructing requests for {len(ordered_selected_slides)} slides...")
        for slide_to_copy in ordered_selected_slides:
            try:
                # Get the full details of the source slide.
                source_slide_page = slides_service.presentations().pages().get(
                    presentationId=slide_to_copy['presentation_id'],
                    pageObjectId=slide_to_copy['slide_id']
                ).execute()

                new_slide_id = f"copied_{slide_to_copy['slide_id']}"

                # Request to create a new slide with a title placeholder.
                new_title_shape_id = f"title_for_{new_slide_id}"
                # By omitting slideLayoutReference, we let the Slides API choose a default layout from the master.
                # This is robust against custom themes that may not have a 'BLANK' layout.
                requests.append({'createSlide': {'objectId': new_slide_id}})

                # Manually create a text box to act as the title for the source link.
                requests.append({
                    'createShape': {
                        'objectId': new_title_shape_id,
                        'shapeType': 'TEXT_BOX',
                        'elementProperties': {
                            'pageObjectId': new_slide_id,
                            'size': {'height': {'magnitude': 500000, 'unit': 'EMU'}, 'width': {'magnitude': 8500000, 'unit': 'EMU'}},
                            'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 300000, 'translateY': 200000, 'unit': 'EMU'}
                        }
                    }
                })

                # Add request to set the new title with source information.
                new_title_text = f"Source: {slide_to_copy['presentation_name']} (Slide {slide_to_copy['slide_number']})"
                requests.append({
                    'insertText': {'objectId': new_title_shape_id, 'text': new_title_text}
                })

                # Add a request to make the source text a hyperlink to the original slide.
                source_slide_url = f"https://docs.google.com/presentation/d/{slide_to_copy['presentation_id']}/edit#slide=id.{slide_to_copy['slide_id']}"
                requests.append({
                    'updateTextStyle': {
                        'objectId': new_title_shape_id,
                        'style': {
                            'link': {'url': source_slide_url}
                        },
                        'textRange': {'type': 'ALL'},
                        'fields': 'link'
                    }
                })

                # Request to copy the background from the source slide.
                source_properties = source_slide_page.get('slideProperties', {})
                if source_properties.get('slideBackgroundFill'):
                    requests.append({
                        'updatePageProperties': {
                            'objectId': new_slide_id,
                            'pageProperties': {'pageBackgroundFill': source_properties['slideBackgroundFill']},
                            'fields': 'pageBackgroundFill'
                        }
                    })

                # Create requests to copy each element (shapes, text, images).
                if source_slide_page.get('pageElements'):
                    for element in source_slide_page['pageElements']:
                        if 'placeholder' in element.get('shape', {}):
                            continue # Skip placeholders as they are part of the layout.

                        new_element = copy.deepcopy(element)
                        new_element['objectId'] = f"copied_{element['objectId']}"
                        
                        if 'shape' in new_element:
                            # Use .get() to safely access 'shapeType' and provide a default
                            # value if it's missing, preventing a KeyError.
                            shape_type = new_element['shape'].get('shapeType', 'RECTANGLE')
                            requests.append({
                                'createShape': {
                                    'objectId': new_element['objectId'], 
                                    'elementProperties': {'pageObjectId': new_slide_id, 'size': new_element.get('size'), 'transform': new_element.get('transform')}, 
                                    'shapeType': shape_type
                                }
                            })

                            # NEW: Add a request to update the shape's properties (fill, outline, etc.) to fix formatting.
                            if 'shapeProperties' in new_element['shape']:
                                requests.append({
                                    'updateShapeProperties': {
                                        'objectId': new_element['objectId'],
                                        'shapeProperties': new_element['shape']['shapeProperties'],
                                        'fields': 'shapeBackgroundFill,outline,shadow'  # Use a specific field mask to avoid read-only fields.
                                    }
                                })

                            if 'text' in new_element['shape']:
                                full_text = _get_text_from_element(new_element)
                                if full_text:
                                    requests.append({'insertText': {'objectId': new_element['objectId'], 'text': full_text, 'insertionIndex': 0}})
                                    # NEW: Apply the style from the first text run to the entire shape to improve text formatting.
                                    first_style = next((te['textRun']['style'] for te in new_element['shape']['text'].get('textElements', []) if te.get('textRun') and te['textRun'].get('style')), None)
                                    if first_style:
                                        requests.append({'updateTextStyle': {
                                            'objectId': new_element['objectId'],
                                            'style': first_style,
                                            'textRange': {'type': 'ALL'},
                                            'fields': 'bold,italic,underline,strikethrough,fontFamily,fontSize,foregroundColor,backgroundColor' # Use a specific field mask.
                                        }})
                        elif 'image' in new_element:
                            requests.append({'createImage': {'objectId': new_element['objectId'], 'url': new_element['image']['contentUrl'], 'elementProperties': {'pageObjectId': new_slide_id, 'size': new_element.get('size'), 'transform': new_element.get('transform')}}})
                            
            except HttpError as err:
                logging.error(f"Could not copy slide {slide_to_copy['slide_id']}: {err}")

        # Execute all requests in a single batch update.
        if requests:
            slides_service.presentations().batchUpdate(presentationId=presentation_id, body={'requests': requests}).execute()

        # Share presentation (only for new presentations) and prepare response
        if not slides_to_update_url:
            logging.info("Finished constructing new presentation.")
            user_email_to_share = os.environ.get('DRIVE_SHARE_EMAIL')
            if user_email_to_share:
                drive_service.permissions().create(fileId=presentation_id, body={'type': 'user', 'role': 'writer', 'emailAddress': user_email_to_share}, sendNotificationEmail=True).execute()
            else:
                drive_service.permissions().create(fileId=presentation_id, body={'type': 'anyone', 'role': 'reader'}).execute()
        
        final_url = slides_to_update_url or f'https://docs.google.com/presentation/d/{presentation_id}/edit'
        response_data = {
            'message': 'Presentation updated successfully' if slides_to_update_url else 'Presentation created successfully',
            'presentation_id': presentation_id,
            'presentation_url': final_url
        }
        logging.info(f"Successfully processed presentation: {final_url}")
        return json.dumps(response_data)

    except HttpError as err:
        error_content = err.content.decode('utf-8')
        logging.error(f"An HttpError occurred: {error_content}", exc_info=True)
        return f"An API error occurred: {error_content}", getattr(err, 'resp', {}).get('status', 500)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
        return f"An unexpected error occurred: {e}", 500