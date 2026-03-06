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

# Credentials live at pipeline/ level (shared across stages)
_PIPELINE_DIR = os.path.join(os.path.dirname(__file__), "..")
_CREDENTIALS_FILE = os.path.join(_PIPELINE_DIR, "credentials.json")
_TOKEN_FILE = os.path.join(_PIPELINE_DIR, "token.json")

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
    if os.path.exists(_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(_TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {e}. Please delete token.json and re-authenticate.")
                os.remove(_TOKEN_FILE)
                return get_drive_service()
        else:
            flow = InstalledAppFlow.from_client_secrets_file(_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(_TOKEN_FILE, 'w') as token:
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
        text = a.text.strip().replace('\n', ' ')
        
        # Link heuristics differ slightly between 10 and 12
        expected_path_part = "sr-secondary-courses" if is_class_12 else "secondary-courses"
        
        if "online-course-material" in href.lower() and expected_path_part in href.lower() and text:
            # Avoid the header links etc.
            if len(text) > 3 and "Secondary" not in text:
                link = urljoin(BASE_URL, href)
                
                # Filter out all non-Hindi/English language subjects
                language_subjects = ['urdu', 'bengali', 'tamil', 'odia', 'punjabi', 'sanskrit',
                                    'arabic', 'sindhi', 'persian', 'bhoti', 'malayalam', 'kannada',
                                    'telugu', 'marathi', 'assamese', 'gujarati', 'regional languages',
                                    'gujarati medium', 'bengali medium', 'urdu medium']
                if any(lang in text.lower() for lang in language_subjects):
                    continue

                if link not in [s['url'] for s in subjects]:
                    subjects.append({"name": text, "url": link})
    
    # Deduplicate old/new curriculums (keep the "New" ones, discard the old ones for the same subject)
    filtered_subjects = []
    # group by the base subject (e.g. "Hindi (301)")
    subject_map = {}
    for sub in subjects:
        # Extract base like "Hindi (301)" from "Hindi (301)-New (effective from..."
        match = re.match(r'([A-Za-z ]+\(\d+\))', sub['name'])
        if match:
            base_name = match.group(1).strip()
            # If we haven't seen it, or this one is explicitly marked "New", replace the old one
            if base_name not in subject_map or "new" in sub['name'].lower():
                subject_map[base_name] = sub
        else:
            # If it doesn't match the pattern (like "History"), just keep it
            filtered_subjects.append(sub)
            
    filtered_subjects.extend(subject_map.values())
    
    print(f"Debug: Filtered down to {len(filtered_subjects)} subjects.")
    return filtered_subjects

def is_english_chapter(text, href, subject_name):
    text_lower = text.lower()
    href_lower = href.lower()
    subject_lower = subject_name.lower()

    # Determine if this is a language subject (like Hindi, Bengali, Arabic, Sanskrti) where we SHOULD NOT strictly enforce English
    # English is excluded from this list since it's an English subject, so the strict English filter applies automatically anyway.
    language_subjects = ['hindi', 'urdu', 'bengali', 'tamil', 'odia', 'punjabi', 'sanskrit', 'arabic', 'sindhi', 'persian', 'bhoti', 'malayalam', 'kannada', 'telugu', 'marathi', 'assamese', 'gujarati']
    is_lang_subject = any(lang in subject_lower for lang in language_subjects)

    # 1. Reject if non-English medium folders - ONLY if it's NOT a native language subject itself.
    # Any path segment that indicates a non-English language medium should be rejected.
    non_english_path_segments = [
        '/hindi/', '/urdu/', '/gujarati/', '/bengali/', '/tamil/', '/odia/',
        '/punjabi/', '/assamese/', '/marathi/', '/telugu/', '/malayalam/',
        '/kannada/', '_hindi/', '_urdu/', '_hin/', 'hin_lesson', '_hindi_',
    ]
    if not is_lang_subject:
        for seg in non_english_path_segments:
            if seg in href_lower:
                return False

    # 2. Reject known non-chapter materials (We want this for ALL subjects to avoid downloading junk)
    exclusions = [
        'tma', 'assignment', 'syllabus', 'sample paper', 'question paper',
        'curriculum', 'practical', 'guidelines', 'bifurcation', 'worksheet',
        'ws-', 'ws_', 'learner guide', 'first page', 'inst.pdf', '(tma)',
        'contents', 'content-', 'index', 'front page',  # TOC / index sheets
        'lab manual', 'laboratory manual', 'lab_manual', 'lab-manual', # Lab manuals
        # Site-wide administrative/circular PDFs that appear on every subject page
        'aicte', 'circular', 'equivalency', 'government order', 'govt. order',
        'frequently asked questions', 'faq', 'vocational education programme',
        'employment in public services', 'recognition of national institute',
        'tamil nadu', 'admission in aicte',
    ]
    if any(ex in text_lower or ex in href_lower for ex in exclusions):
        return False

    # 2b. Reject Learner Guide files (abbreviated as 'LG-' in filenames/hrefs)
    basename = os.path.basename(href_lower)
    if re.match(r'lg[-_]\d', basename) or re.match(r'lg[-_]\d', text_lower):
        return False

    # 2c. Reject full-book downloads (e.g. book-1.pdf, book1.pdf, book 1, Book-2.pdf)
    if re.match(r'book[-_ ]?\d', basename) or re.search(r'\bbook[-_ ]?\d', text_lower):
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

def extract_chapter_number(text, href):
    """
    Tries to extract a numeric chapter ID from the link text or URL.
    Handles known NIOS patterns like 'Lesson 1', 'L-1NF', '1 - Sets', etc.
    Returns the integer if found, else None.
    """
    text_lower = text.lower()
    basename = os.path.basename(href).lower()

    # Pattern 1: Explicit labels like "Lesson 1", "Lesson - 2", "Chapter 3", "L-4", "L-5NF"
    match = re.search(r'\b(?:lesson|chapter|l)[-_ ]*(\d+)', text_lower)
    if match:
        return int(match.group(1))
        
    match = re.search(r'\b(?:lesson|chapter|l)[-_ ]*(\d+)', basename)
    if match:
        return int(match.group(1))

    # Pattern 2: Leading numbers in text like "1 - Sets", "02 . Matrix"
    match = re.match(r'^(\d+)[ \-:\.]', text_lower)
    if match:
        return int(match.group(1))

    # Pattern 3: Any naked number if it represents the whole text (e.g. just "12")
    match = re.match(r'^(\d+)$', text_lower.strip())
    if match:
        return int(match.group(1))
        
    return None

def get_chapter_pdfs(subject_url, subject_name):
    soup = fetch_content(subject_url)
    if not soup:
        return []

    chapters = []
    seen_urls = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.text.strip().replace('\n', ' ').replace('\r', '')
        
        if href.lower().endswith('.pdf'):
            if is_english_chapter(text, href, subject_name):
                link = urljoin(BASE_URL, href)

                # Deduplicate by canonical URL to prevent English + Hindi versions
                # of the same lesson both sneaking through under different names
                if link in seen_urls:
                    continue
                seen_urls.add(link)

                # Format filename predictably: "Chapter X.pdf"
                chapter_num = extract_chapter_number(text, href)
                if chapter_num is not None:
                    final_name = f"Chapter {chapter_num}.pdf"
                else:
                    # Fallback for unnumbered chapters
                    clean_text = "".join(x for x in text if x.isalnum() or x in " -_.").strip()
                    if not clean_text or len(clean_text) < 3:
                        clean_text = os.path.basename(unquote(href)).split('?')[0]
                    
                    if not clean_text.lower().endswith('.pdf'):
                        clean_text += ".pdf"
                        
                    final_name = f"Extra - {clean_text}"

                # Append if not duplicate filename
                if final_name not in [c['name'] for c in chapters]:
                    chapters.append({"name": final_name, "url": link})

    return chapters

def get_subject_stream(subject_name):
    """
    Categorizes a NIOS subject based on its name/code into standard academic streams.
    """
    name_lower = subject_name.lower()
    
    science_keywords = ['physics', 'chemistry', 'biology', 'mathematics', 'computer science', 'science and technology']
    commerce_keywords = ['accountancy', 'business studies', 'economics']
    humanities_keywords = ['history', 'geography', 'political science', 'psychology', 'sociology', 'painting', 'mass communication', 'indian culture']
    language_keywords = ['hindi', 'english', 'sanskrit', 'urdu', 'bengali', 'tamil', 'odia', 'punjabi', 'arabic', 'persian', 'malayalam']

    if any(k in name_lower for k in science_keywords):
        return "Science"
    elif any(k in name_lower for k in commerce_keywords):
        return "Commerce"
    elif any(k in name_lower for k in humanities_keywords):
        return "Humanities"
    elif any(k in name_lower for k in language_keywords):
        return "Languages"
    else:
        return "Vocational & Others"

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
        
    print(f"Found {len(subjects)} subjects in total.")

    # Categorize subjects
    streams = {
        "Science": [],
        "Commerce": [],
        "Humanities": [],
        "Languages": [],
        "Vocational & Others": []
    }
    
    for sub in subjects:
        stream = get_subject_stream(sub['name'])
        streams[stream].append(sub)

    print("\n--- Available Streams ---")
    stream_names = list(streams.keys())
    for i, s_name in enumerate(stream_names, 1):
        print(f"{i}) {s_name} ({len(streams[s_name])} subjects)")
    print(f"{len(stream_names) + 1}) ALL Streams")
    
    stream_choice = input(f"\nSelect Stream (1-{len(stream_names) + 1}): ").strip()
    
    selected_subjects = []
    selected_stream_name = "ALL"
    
    try:
        choice_idx = int(stream_choice) - 1
        if 0 <= choice_idx < len(stream_names):
            selected_stream_name = stream_names[choice_idx]
            stream_subjects = streams[selected_stream_name]
            
            print(f"\n--- Subjects in {selected_stream_name} ---")
            for i, sub in enumerate(stream_subjects, 1):
                print(f"{i}) {sub['name']}")
            print(f"{len(stream_subjects) + 1}) Select ALL in {selected_stream_name}")
            
            sub_choice = input(f"\nEnter subject numbers (comma separated) or '{len(stream_subjects) + 1}' for ALL: ").strip()
            
            if str(len(stream_subjects) + 1) in sub_choice.split(','):
                selected_subjects = stream_subjects
            else:
                indices = [int(x.strip()) - 1 for x in sub_choice.split(',') if x.strip().isdigit()]
                for idx in indices:
                    if 0 <= idx < len(stream_subjects):
                        selected_subjects.append(stream_subjects[idx])
        elif choice_idx == len(stream_names):
            selected_subjects = subjects
            selected_stream_name = "ALL"
        else:
            print("Invalid choice.")
            return
    except ValueError:
        print("Invalid input.")
        return

    if not selected_subjects:
        print("No subjects selected. Exiting.")
        return
        
    print(f"\nProceeding with {len(selected_subjects)} subjects from {selected_stream_name}.")
    
    # Initialize Drive & Registry
    service = get_drive_service()
    nios_root_id = get_or_create_folder(service, "NIOS Backup")
    class_folder_id = get_or_create_folder(service, class_name, nios_root_id)
    registry = load_registry()

    # Process in batches of 3
    batch_size = 3
    for i in range(0, len(selected_subjects), batch_size):
        batch = selected_subjects[i:i+batch_size]
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
                
            stream_name = get_subject_stream(subject['name'])
            stream_folder_id = get_or_create_folder(service, stream_name, class_folder_id)
            subject_folder_id = get_or_create_folder(service, subject['name'], stream_folder_id)
            
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
