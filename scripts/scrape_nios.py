import os
import io
import time
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']
BASE_URL = "https://nios.ac.in"
REGISTRY_FILE = "downloads_registry.json"

def load_registry():
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_registry(registry):
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, indent=4)

def get_drive_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {e}. Please delete token.json and re-authenticate.")
                os.remove("token.json")
                return get_drive_service()
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def get_or_create_folder(service, folder_name, parent_id=None):
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    
    results = service.files().list(q=query, spaces='drive', fields='nextPageToken, files(id, name)').execute()
    items = results.get('files', [])
    
    if items:
        return items[0]['id']
    else:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]
        
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

def fetch_content(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
    }
    for _ in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            print(f"Failed to fetch {url}: {e}. Retrying...")
            time.sleep(2)
    return None

def scrape_subjects(course_url, is_class_12=False):
    soup = fetch_content(course_url)
    if not soup:
        print("Debug: Failed to fetch the soup for course_url.")
        return []

    subjects = []
    print(f"Debug: Found {len(soup.find_all('a', href=True))} links on the page.")
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.text.strip()
        
        # Link heuristics differ slightly between 10 and 12
        expected_path_part = "sr-secondary-courses" if is_class_12 else "secondary-courses"
        
        if "online-course-material" in href.lower() and expected_path_part in href.lower() and text:
            # Avoid the header links etc.
            if len(text) > 3 and "Secondary" not in text:
                link = urljoin(BASE_URL, href)
                if link not in [s['url'] for s in subjects]:
                    subjects.append({"name": text, "url": link})
    print(f"Debug: Filtered down to {len(subjects)} subjects.")
    return subjects

def is_english_chapter(text, href, subject_name):
    text_lower = text.lower()
    href_lower = href.lower()
    subject_lower = subject_name.lower()

    # Determine if this is a language subject (like Hindi, Bengali, Arabic, Sanskrti) where we SHOULD NOT strictly enforce English
    # English is excluded from this list since it's an English subject, so the strict English filter applies automatically anyway.
    language_subjects = ['hindi', 'urdu', 'bengali', 'tamil', 'odia', 'punjabi', 'sanskrit', 'arabic', 'sindhi', 'persian', 'bhoti', 'malayalam', 'kannada', 'telugu', 'marathi', 'assamese', 'gujarati']
    is_lang_subject = any(lang in subject_lower for lang in language_subjects)

    # 1. Reject if non-english medium folders - ONLY if it's NOT a native language subject itself.
    if not is_lang_subject:
        for lang in ['/hindi/', '/urdu/', '/gujarati/', '/bengali/', '/tamil/', '/odia/', '/punjabi/', '/assamese/', '/marathi/', '/telugu/', '/malayalam/', '/kannada/']:
            if lang in href_lower:
                return False

    # 2. Reject known non-chapter materials (We want this for ALL subjects to avoid downloading junk)
    exclusions = [
        'tma', 'assignment', 'syllabus', 'sample paper', 'question paper',
        'curriculum', 'practical', 'guidelines', 'bifurcation', 'worksheet', 
        'ws-', 'ws_', 'learner guide', 'first page', 'inst.pdf', '(tma)', 'book 1', 'book 2', 'book 3' # Full books
    ]
    if any(ex in text_lower or ex in href_lower for ex in exclusions):
        return False

    # 3. Check if it looks like a full book download instead of chapter
    if "download book" in text_lower or "part1.zip" in href_lower or "whole" in text_lower:
        return False
        
    # 4. Must have some english alphabetic text, UNLESS it's a native language subject,
    # in which case we tolerate non-ASCII text natively (like Devanagari numerals, text, etc).
    if not is_lang_subject:
        # Reject if devanagari/other scripts in text
        if re.search(r'[\u0900-\u097F]', text):
            return False
            
        if not re.search(r'[A-Za-z]', text):
            return False

    return True

def get_chapter_pdfs(subject_url, subject_name):
    soup = fetch_content(subject_url)
    if not soup:
        return []

    chapters = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.text.strip().replace('\n', ' ').replace('\r', '')
        
        if href.lower().endswith('.pdf'):
            if is_english_chapter(text, href, subject_name):
                link = urljoin(BASE_URL, href)
                
                # Try to use text as filename, fallback to url part
                clean_text = "".join(x for x in text if x.isalnum() or x in " -_.").strip()
                if not clean_text or len(clean_text) < 3:
                    clean_text = os.path.basename(unquote(href)).split('?')[0]
                    
                if not clean_text.lower().endswith('.pdf'):
                    clean_text += ".pdf"

                # Deduplicate chapters
                if clean_text not in [c['name'] for c in chapters]:
                    chapters.append({"name": clean_text, "url": link})

    return chapters

def main():
    print("Welcome to NIOS Google Drive Scraper!")
    print("1) Class 10 (Secondary)")
    print("2) Class 12 (Senior Secondary)")
    
    choice = input("Select Class (1 or 2): ").strip()
    if choice == '1':
        class_name = "Class 10"
        json_file = "subjects_10.json"
    elif choice == '2':
        class_name = "Class 12"
        json_file = "subjects_12.json"
    else:
        print("Invalid choice. Exiting.")
        return

    print(f"\nLoading subjects from {json_file}...")
    try:
        with open(json_file, 'r') as f:
            subjects = json.load(f)
    except Exception as e:
        print(f"Failed to load subject configuration {json_file}: {e}")
        print("Please ensure you generate and place the subject JSON files first!")
        return
    if not subjects:
        print("Failed to fetch subjects. Exiting.")
        return
        
    print(f"Found {len(subjects)} subjects.")
    
    # Initialize Drive & Registry
    service = get_drive_service()
    nios_root_id = get_or_create_folder(service, "NIOS Backup")
    class_folder_id = get_or_create_folder(service, class_name, nios_root_id)
    registry = load_registry()

    # Process in batches of 3
    batch_size = 3
    for i in range(0, len(subjects), batch_size):
        batch = subjects[i:i+batch_size]
        print(f"\n\n--- Next Batch ---")
        for idx, sub in enumerate(batch, 1):
            print(f"  {idx}. {sub['name']}")
        
        ans = input("\nProcess this batch? (y / n / quit): ").strip().lower()
        if ans in ['q', 'quit']:
            print("Exiting...")
            break
        elif ans != 'y':
            print("Skipping batch...")
            continue
            
        for subject in batch:
            print(f"\n-> Scraping Subject: {subject['name']}")
            chapters = get_chapter_pdfs(subject['url'], subject['name'])
            print(f"   Found {len(chapters)} valid chapter(s).")
            
            if not chapters:
                continue
                
            subject_folder_id = get_or_create_folder(service, subject['name'], class_folder_id)
            for chapter in chapters:
                registry_key = f"{class_name}_{subject['name']}_{chapter['name']}"
                
                if registry_key in registry and registry[registry_key] == "SUCCESS":
                    print(f"   [SKIPPED] {chapter['name']} (Already downloaded)")
                    continue
                    
                print(f"   [DOWNLOADING] {chapter['name']} ...")
                try:
                    pdf_resp = requests.get(chapter['url'], timeout=60)
                    pdf_resp.raise_for_status()
                    
                    print(f"   [UPLOADING] {chapter['name']} ...")
                    file_metadata = {
                        'name': chapter['name'],
                        'parents': [subject_folder_id]
                    }
                    fh = io.BytesIO(pdf_resp.content)
                    media = MediaIoBaseUpload(fh, mimetype='application/pdf', resumable=True)
                    service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                    
                    registry[registry_key] = "SUCCESS"
                    save_registry(registry)
                    print(f"   [SUCCESS] {chapter['name']}")
                    
                except Exception as e:
                    print(f"   [ERROR] Failed {chapter['name']}: {e}")
                    registry[registry_key] = f"ERROR: {str(e)}"
                    save_registry(registry)

    print("\nAll requested batches processed!")

if __name__ == '__main__':
    main()
