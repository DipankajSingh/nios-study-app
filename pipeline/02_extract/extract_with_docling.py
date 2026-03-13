#!/usr/bin/env python3

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import hashlib
import traceback
import gc
import subprocess
from dataclasses import dataclass

# Install docling if not available (Kaggle environment)
def install_docling():
    """Install docling in Kaggle environment if not already installed."""
    try:
        import docling
        print("✓ Docling already installed")
    except ImportError:
        print("📦 Installing Docling...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "docling", "--quiet"])
        print("✓ Docling installed successfully")

# Install docling first
install_docling()

# Now import docling
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc import PictureItem, TableItem

# No schema classes needed - using raw Docling JSON output

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/kaggle/working/extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ExtractionConfig:
    """Configuration for the extraction process."""
    input_base_path: str = "/kaggle/input/datasets/dipankaj/nios-chapter-pdfs"
    output_base_path: str = "/kaggle/working/extracted_chapters"
    images_base_path: str = "/kaggle/working/chapter_images"
    resume_file: str = "/kaggle/working/extraction_progress.json"
    max_image_size: int = 1024 * 1024 * 5  # 5MB max per image

class ProgressTracker:
    """Tracks extraction progress for resume capability."""
    
    def __init__(self, resume_file: str):
        self.resume_file = resume_file
        self.progress = self._load_progress()
    
    def _load_progress(self) -> Dict:
        """Load existing progress from file."""
        if os.path.exists(self.resume_file):
            try:
                with open(self.resume_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load progress file: {e}")
        return {"completed_files": [], "failed_files": [], "current_subject": None}
    
    def save_progress(self):
        """Save current progress to file."""
        try:
            with open(self.resume_file, 'w') as f:
                json.dump(self.progress, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")
    
    def is_completed(self, file_path: str) -> bool:
        """Check if file was already processed."""
        return file_path in self.progress.get("completed_files", [])
    
    def is_failed(self, file_path: str) -> bool:
        """Check if file previously failed."""
        return file_path in self.progress.get("failed_files", [])
    
    def mark_completed(self, file_path: str):
        """Mark file as completed."""
        if "completed_files" not in self.progress:
            self.progress["completed_files"] = []
        if file_path not in self.progress["completed_files"]:
            self.progress["completed_files"].append(file_path)
        self.save_progress()
    
    def mark_failed(self, file_path: str):
        """Mark file as failed."""
        if "failed_files" not in self.progress:
            self.progress["failed_files"] = []
        if file_path not in self.progress["failed_files"]:
            self.progress["failed_files"].append(file_path)
        self.save_progress()

class ImageExtractor:
    """Enhanced image extractor with context linking for study app usage."""
    
    def __init__(self, base_path: str, max_size: int):
        self.base_path = Path(base_path)
        self.max_size = max_size
        self.base_path.mkdir(parents=True, exist_ok=True)
        
    def extract_images_with_context(self, doc_result, chapter_id: str) -> List[Dict]:
        """Extract images and link them to nearest heading + text context."""
        images_dir = self.base_path / chapter_id
        images_dir.mkdir(exist_ok=True)
        
        extracted_images = []
        
        try:
            # Get document structure for context linking
            document_elements = self._get_document_elements(doc_result)
            
            # Extract page images first
            self._extract_page_images(doc_result, images_dir, chapter_id, document_elements, extracted_images)
            
            # Extract pictures and tables using iterate_items
            self._extract_document_elements(doc_result, images_dir, chapter_id, document_elements, extracted_images)
                            
        except Exception as e:
            logger.error(f"Error extracting images for {chapter_id}: {e}")
            logger.error(traceback.format_exc())
        
        logger.info(f"Successfully extracted {len(extracted_images)} images with context for {chapter_id}")
        return extracted_images
    
    def _extract_page_images(self, doc_result, images_dir: Path, chapter_id: str, 
                           document_elements: List[Dict], extracted_images: List[Dict]):
        """Extract page images from document pages."""
        try:
            # Access pages dict (page_no -> Page object)
            if hasattr(doc_result.document, 'pages'):
                for page_no, page in doc_result.document.pages.items():
                    if hasattr(page, 'image') and hasattr(page.image, 'pil_image'):
                        image_path = images_dir / f"page_{page_no:03d}.png"
                        
                        # Save page image
                        try:
                            page.image.pil_image.save(image_path, 'PNG')
                            if image_path.stat().st_size > self.max_size:
                                logger.warning(f"Page image {image_path} exceeds max size, skipping")
                                image_path.unlink()
                                continue
                                
                            # Find context for page
                            context = self._find_page_context(page_no, document_elements)
                            
                            extracted_images.append({
                                'type': 'page_image',
                                'path': str(image_path.relative_to(self.base_path.parent)),
                                'filename': image_path.name,
                                'page': page_no,
                                'nearest_heading': context.get('heading', ''),
                                'nearest_text': context.get('text', ''),
                                'context_type': 'page'
                            })
                            
                        except Exception as e:
                            logger.error(f"Error saving page {page_no} image: {e}")
                            
        except Exception as e:
            logger.debug(f"Error extracting page images: {e}")
    
    def _extract_document_elements(self, doc_result, images_dir: Path, chapter_id: str,
                                 document_elements: List[Dict], extracted_images: List[Dict]):
        """Extract images from pictures and tables using iterate_items."""
        try:
            picture_counter = 0
            table_counter = 0
            
            # Use iterate_items to go through document elements
            for element, level in doc_result.document.iterate_items():
                try:
                    if isinstance(element, PictureItem):
                        picture_counter += 1
                        image_path = images_dir / f"picture_{picture_counter:03d}.png"
                        
                        # Get image using Docling's method
                        try:
                            picture_image = element.get_image(doc_result.document)
                            picture_image.save(image_path, 'PNG')
                            
                            if image_path.stat().st_size > self.max_size:
                                logger.warning(f"Picture {picture_counter} exceeds max size, skipping")
                                image_path.unlink()
                                continue
                            
                            # Find context
                            context = self._find_element_context(element, document_elements)
                            
                            extracted_images.append({
                                'type': 'picture',
                                'path': str(image_path.relative_to(self.base_path.parent)),
                                'filename': image_path.name,
                                'index': picture_counter - 1,
                                'nearest_heading': context.get('heading', ''),
                                'nearest_text': context.get('text', ''),
                                'context_type': 'picture'
                            })
                            
                        except Exception as e:
                            logger.debug(f"Error extracting picture {picture_counter}: {e}")
                            
                    elif isinstance(element, TableItem):
                        # Extract table images too (they can have visual representations)
                        table_counter += 1
                        try:
                            if hasattr(element, 'get_image'):
                                image_path = images_dir / f"table_{table_counter:03d}.png"
                                table_image = element.get_image(doc_result.document)
                                table_image.save(image_path, 'PNG')
                                
                                if image_path.stat().st_size <= self.max_size:
                                    context = self._find_element_context(element, document_elements)
                                    
                                    extracted_images.append({
                                        'type': 'table_image',
                                        'path': str(image_path.relative_to(self.base_path.parent)),
                                        'filename': image_path.name,
                                        'index': table_counter - 1,
                                        'nearest_heading': context.get('heading', ''),
                                        'nearest_text': context.get('text', ''),
                                        'context_type': 'table'
                                    })
                                else:
                                    image_path.unlink()
                                    
                        except Exception as e:
                            logger.debug(f"Error extracting table {table_counter} image: {e}")
                            
                except Exception as e:
                    logger.debug(f"Error processing document element: {e}")
                    
        except Exception as e:
            logger.debug(f"Error in document elements iteration: {e}")
    
    def _find_page_context(self, page_no: int, document_elements: List[Dict]) -> Dict:
        """Find context for page images."""
        context = {'heading': '', 'text': '', 'type': 'page'}
        
        try:
            # Simple approach: use first few text elements as context
            if document_elements:
                # Find first heading-like element
                for element in document_elements[:10]:  # Check first 10 elements
                    if 'heading' in element.get('type', '').lower():
                        context['heading'] = element.get('text', '')[:100]
                        break
                
                # Use first substantial text element 
                for element in document_elements[:5]:
                    text = element.get('text', '').strip()
                    if len(text) > 20:  # Substantial text
                        context['text'] = text[:200] + "..." if len(text) > 200 else text
                        break
                        
        except Exception as e:
            logger.debug(f"Error finding page context: {e}")
            
        return context
    
    def _find_element_context(self, element, document_elements: List[Dict]) -> Dict:
        """Find context for document elements (pictures/tables)."""
        context = {'heading': '', 'text': '', 'type': 'element'}
        
        try:
            # Try to find nearest text based on bounding box or order
            if document_elements:
                # Simple approach: use middle elements as representative context
                mid_idx = len(document_elements) // 2
                if mid_idx < len(document_elements):
                    mid_element = document_elements[mid_idx]
                    context['text'] = mid_element.get('text', '')[:200]
                
                # Find latest heading
                for element_data in reversed(document_elements):
                    if 'heading' in element_data.get('type', '').lower():
                        context['heading'] = element_data.get('text', '')
                        break
                        
        except Exception as e:
            logger.debug(f"Error finding element context: {e}")
            
        return context
    
    def _serialize_item(self, item) -> Dict:
        """Serialize Pydantic item to JSON-compatible dict."""
        try:
            if hasattr(item, 'model_dump'):
                return item.model_dump()
            elif hasattr(item, 'dict'):
                return item.dict()
            else:
                # Fallback for simple objects
                return str(item)
        except Exception as e:
            logger.debug(f"Error serializing item: {e}")
            return str(item)
    def _get_document_elements(self, doc_result) -> List[Dict]:
        """Extract ordered document elements (headings, paragraphs) for context linking."""
        elements = []
        
        try:
            # Get text elements from document structure
            if hasattr(doc_result.document, 'texts'):
                for i, text_item in enumerate(doc_result.document.texts):
                    elements.append({
                        'index': i,
                        'type': getattr(text_item, 'label', 'text'),
                        'text': getattr(text_item, 'text', ''),
                        'bbox': getattr(text_item, 'bbox', None)
                    })
            
            # Fallback: Extract from markdown structure
            if not elements:
                try:
                    markdown_text = doc_result.document.export_to_markdown()
                    elements = self._parse_markdown_structure(markdown_text)
                except Exception as e:
                    logger.debug(f"Error getting markdown: {e}")
                        
        except Exception as e:
            logger.debug(f"Error getting document elements: {e}")
            
        return elements
    
    def _parse_markdown_structure(self, markdown_text: str) -> List[Dict]:
        """Parse markdown to extract headings and paragraphs."""
        import re
        elements = []
        lines = markdown_text.split('\n')
        
        current_heading = ""
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Detect headings
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2)
                current_heading = text
                elements.append({
                    'line': i,
                    'type': f'heading_{level}',
                    'text': text,
                    'heading_context': text
                })
            elif line and not line.startswith('#'):
                # Regular paragraph
                elements.append({
                    'line': i,
                    'type': 'paragraph', 
                    'text': line,
                    'heading_context': current_heading
                })
                
        return elements
    
    def _extract_picture_with_context(self, pic_data, images_dir: Path, chapter_id: str, 
                                    img_index: int, document_elements: List[Dict]) -> Optional[Dict]:
        """Extract single picture with context linking."""
        try:
            image_path = images_dir / f"image_{img_index+1:03d}.png"
            
            # Try to save the image
            if not self._save_image_data(pic_data, image_path):
                return None
                
            # Find nearest context
            context = self._find_image_context(img_index, document_elements, 'picture')
            
            # Return image info with context
            return {
                'type': 'picture',
                'path': str(image_path.relative_to(self.base_path.parent)),
                'filename': image_path.name,
                'index': img_index,
                'nearest_heading': context.get('heading', ''),
                'nearest_text': context.get('text', ''),
                'context_type': context.get('type', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Error extracting picture {img_index}: {e}")
            return None
    
    def _extract_page_image_with_context(self, img_data, images_dir: Path, chapter_id: str,
                                       page_idx: int, img_index: int, document_elements: List[Dict]) -> Optional[Dict]:
        """Extract page image with context linking.""" 
        try:
            image_path = images_dir / f"page_{page_idx+1}_image_{img_index+1:03d}.png"
            
            # Try to save the image
            if not self._save_image_data(img_data, image_path):
                return None
                
            # Find context based on page
            context = self._find_image_context(img_index, document_elements, 'page', page_idx)
            
            return {
                'type': 'page_image',
                'path': str(image_path.relative_to(self.base_path.parent)), 
                'filename': image_path.name,
                'page': page_idx + 1,
                'index': img_index,
                'nearest_heading': context.get('heading', ''),
                'nearest_text': context.get('text', ''),
                'context_type': context.get('type', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Error extracting page {page_idx} image {img_index}: {e}")
            return None
    
    def _find_image_context(self, img_index: int, document_elements: List[Dict], 
                          img_type: str, page_idx: int = None) -> Dict:
        """Find nearest heading and text block for image context."""
        context = {'heading': '', 'text': '', 'type': 'unknown'}
        
        try:
            # Filter elements by page if specified
            if page_idx is not None:
                page_elements = [e for e in document_elements if e.get('page') == page_idx]
            else:
                page_elements = document_elements
                
            if not page_elements:
                return context
            
            # Find nearest heading (working backwards through document flow)
            nearest_heading = ""
            for element in reversed(page_elements):
                if 'heading' in element.get('type', ''):
                    nearest_heading = element.get('text', '')
                    break
            
            # Find nearest text block (closest by position)
            if page_elements:
                # Simple approach: take middle element as nearest text
                mid_idx = len(page_elements) // 2
                if mid_idx < len(page_elements):
                    nearest_element = page_elements[mid_idx]
                    context = {
                        'heading': nearest_heading or nearest_element.get('heading_context', ''),
                        'text': nearest_element.get('text', '')[:200] + "..." if len(nearest_element.get('text', '')) > 200 else nearest_element.get('text', ''), 
                        'type': nearest_element.get('type', 'paragraph')
                    }
                    
        except Exception as e:
            logger.debug(f"Error finding image context: {e}")
            
        return context
    
    def _save_image_data(self, img_obj, image_path: Path) -> bool:
        """Save image using multiple strategies."""
        # Strategy 1: Direct PIL image
        if self._save_pil_image(img_obj, image_path):
            return True
            
        # Strategy 2: Check nested data
        if hasattr(img_obj, 'data'):
            if isinstance(img_obj.data, dict):
                for key in ['image', 'pil_image', 'picture', 'content']:
                    if key in img_obj.data:
                        if self._save_pil_image(img_obj.data[key], image_path):
                            return True
                if self._save_base64_or_bytes(img_obj.data, image_path):
                    return True
            else:
                if self._save_pil_image(img_obj.data, image_path):
                    return True
                    
        # Strategy 3: Direct attributes
        for attr in ['image', 'pil_image', 'picture', 'img']:
            if hasattr(img_obj, attr):
                if self._save_pil_image(getattr(img_obj, attr), image_path):
                    return True
                    
        return False
    
    def _save_pil_image(self, img_obj, image_path: Path) -> bool:
        """Try to save object as PIL image."""
        try:
            # Check if it's already a PIL image
            if hasattr(img_obj, 'save') and hasattr(img_obj, 'size'):
                img_obj.save(image_path, 'PNG')
                if image_path.stat().st_size > self.max_size:
                    logger.warning(f"Image {image_path} exceeds max size, skipping")
                    image_path.unlink()
                    return False
                return True
                
            # Try to convert to PIL if it has image data
            from PIL import Image
            if hasattr(img_obj, 'tobytes'):
                # Convert numpy array or similar
                img = Image.fromarray(img_obj)
                img.save(image_path, 'PNG')
                return True
                
        except Exception as e:
            logger.debug(f"Failed to save as PIL image: {e}")
            
        return False
    
    def _save_base64_or_bytes(self, data, image_path: Path) -> bool:
        """Try to save base64 encoded or binary image data."""
        try:
            import base64
            from PIL import Image
            from io import BytesIO
            
            # Handle various data formats
            if isinstance(data, dict):
                for key in ['content', 'data', 'bytes', 'image_data']:
                    if key in data:
                        return self._save_base64_or_bytes(data[key], image_path)
            
            if isinstance(data, str):
                # Try base64 decoding
                try:
                    # Remove data URL prefix if present
                    if data.startswith('data:'):
                        data = data.split(',', 1)[1]
                    
                    img_bytes = base64.b64decode(data)
                    img = Image.open(BytesIO(img_bytes))
                    img.save(image_path, 'PNG')
                    return True
                except:
                    pass
            
            elif isinstance(data, bytes):
                # Try direct bytes
                try:
                    img = Image.open(BytesIO(data))
                    img.save(image_path, 'PNG')
                    return True
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Failed to save base64/bytes image: {e}")
            
        return False

class NISODoclingExtractor:
    """Main extractor class for NIOS content using Docling with raw JSON output."""
    
    def __init__(self, config: ExtractionConfig):
        self.config = config
        self.progress = ProgressTracker(config.resume_file)
        self.image_extractor = ImageExtractor(config.images_base_path, config.max_image_size)
        
        # Setup output directories
        Path(config.output_base_path).mkdir(parents=True, exist_ok=True)
        Path(config.images_base_path).mkdir(parents=True, exist_ok=True)
        
        # Configure Docling with optimal settings for NIOS PDFs
        self.converter = self._setup_docling_converter()
        
        logger.info("📚 NIOS Docling Extractor initialized (Raw JSON mode)")
        logger.info(f"Input path: {config.input_base_path}")
        logger.info(f"Output path: {config.output_base_path}")
    
    def _setup_docling_converter(self) -> DocumentConverter:
        """Configure Docling converter with optimal settings for academic PDFs."""
        try:
            # Configure pipeline for comprehensive extraction
            pdf_options = PdfPipelineOptions()
            pdf_options.images_scale = 2.0  # Higher quality image extraction
            pdf_options.generate_page_images = True
            pdf_options.generate_picture_images = True
            
            # Initialize converter with optimal settings
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
                }
            )
            
            logger.info("✓ Docling converter configured successfully")
            return converter
            
        except Exception as e:
            logger.warning(f"Could not configure advanced options: {e}")
            # Fallback to basic converter
            return DocumentConverter()
    
    def discover_pdf_files(self) -> List[Tuple[str, Path]]:
        """Discover all PDF files with their chapter identifiers."""
        input_path = Path(self.config.input_base_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input directory not found: {input_path}")
        
        pdf_files = []
        
        # Process both class 10 and class 12
        for class_dir in ["class10", "class12"]:
            class_path = input_path / class_dir
            if not class_path.exists():
                logger.warning(f"Class directory not found: {class_path}")
                continue
                
            # Find all subject directories
            for subject_dir in class_path.iterdir():
                if not subject_dir.is_dir():
                    continue
                    
                subject_id = subject_dir.name
                
                # Find all PDF files in subject directory
                for pdf_file in subject_dir.glob("*.pdf"):
                    chapter_number = self._extract_chapter_number(pdf_file.name)
                    chapter_id = f"{subject_id}-ch{chapter_number:02d}"
                    pdf_files.append((chapter_id, pdf_file))
                    
                logger.info(f"Found {len(list(subject_dir.glob('*.pdf')))} PDFs for {subject_id}")
        
        # Sort by chapter ID for consistent processing order
        pdf_files.sort(key=lambda x: x[0])
        
        total_pdfs = len(pdf_files)
        logger.info(f"📊 Discovered {total_pdfs} PDF chapters total")
        
        return pdf_files
    
    def _extract_chapter_number(self, filename: str) -> int:
        """Extract chapter number from filename for sorting."""
        import re
        match = re.search(r'[Cc]hapter\s*(\d+)', filename)
        return int(match.group(1)) if match else 999
    
    def extract_single_chapter(self, chapter_id: str, pdf_path: Path) -> Optional[Dict]:
        """Extract content from a single PDF chapter and return raw Docling JSON."""
        try:
            logger.info(f"🔍 Processing PDF: {pdf_path}")
            
            # Convert PDF using Docling
            doc_result = self.converter.convert(str(pdf_path))
            
            if not doc_result or not doc_result.document:
                logger.error(f"Docling failed to process: {pdf_path}")
                return None
                
            # Convert Docling result to JSON (keep main content fields)
            docling_json = self._docling_to_json(doc_result)
            
            # Extract images with context
            image_info = self.image_extractor.extract_images_with_context(
                doc_result, chapter_id
            )
            
            # Create enhanced JSON output
            enhanced_json = {
                'chapter_id': chapter_id,
                'source_pdf': str(pdf_path),
                'extracted_at': datetime.now().isoformat(),
                'docling_content': docling_json,
                'image_context': image_info,
                'extraction_stats': {
                    'images_extracted': len(image_info),
                    'text_length': len(docling_json.get('content', '')),
                    'pages': len(docling_json.get('pages', []))
                }
            }
            
            # Log extraction statistics
            stats = enhanced_json['extraction_stats']
            logger.info(f"📊 Extracted: {stats['text_length']:,} chars text, "
                       f"{stats['images_extracted']} images, {stats['pages']} pages")
            
            return enhanced_json
            
        except Exception as e:
            logger.error(f"Error extracting chapter from {pdf_path}: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def _docling_to_json(self, doc_result) -> Dict:
        """Convert Docling result to JSON, keeping main content fields."""
        try:
            # Get the core content using Pydantic model serialization
            json_data = {
                'markdown_content': '',
                'texts': [],
                'tables': [],
                'pictures': [],
                'key_value_items': [],
                'pages': {},
                'metadata': {}
            }
            
            # Export main content as markdown
            try:
                json_data['markdown_content'] = doc_result.document.export_to_markdown()
            except Exception as e:
                logger.debug(f"Error exporting markdown: {e}")
            
            # Export document structure using model_dump
            try:
                docling_dict = doc_result.document.model_dump()
                
                # Keep main content fields
                for key in ['texts', 'tables', 'pictures', 'key_value_items']:
                    if key in docling_dict:
                        # Convert to serializable format
                        items = docling_dict[key]
                        if items:
                            json_data[key] = [self._serialize_item(item) for item in items]
                
                # Handle pages separately (pages is a dict)
                if 'pages' in docling_dict:
                    json_data['pages'] = {str(k): self._serialize_item(v) for k, v in docling_dict['pages'].items()}
                    
            except Exception as e:
                logger.debug(f"Error serializing document: {e}")
            
            # Include source metadata
            try:
                if hasattr(doc_result, 'input') and hasattr(doc_result.input, 'file'):
                    json_data['metadata']['source_file'] = str(doc_result.input.file)
            except:
                pass
                
            return json_data
            
        except Exception as e:
            logger.warning(f"Error converting Docling to JSON: {e}")
            # Fallback: just get markdown content
            try:
                return {
                    'markdown_content': doc_result.document.export_to_markdown(),
                    'texts': [],
                    'tables': [],
                    'pictures': [],
                    'key_value_items': [],
                    'pages': {},
                    'metadata': {'extraction_fallback': True}
                }
            except:
                return {
                    'error': 'Could not extract content', 
                    'texts': [],
                    'tables': [],
                    'pictures': [],
                    'key_value_items': [],
                    'pages': {},
                    'metadata': {}
                }
    
    def save_chapter_json(self, chapter_data: Dict) -> Path:
        """Save chapter data as JSON file."""
        chapter_id = chapter_data.get('chapter_id', 'unknown')
        output_file = Path(self.config.output_base_path) / f"{chapter_id}.json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(chapter_data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"💾 Saved chapter JSON: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Error saving chapter JSON: {e}")
            raise
    
    def run_extraction(self) -> Dict[str, Any]:
        """Run the complete extraction process - one JSON per chapter."""
        logger.info("🚀 Starting NIOS content extraction with Docling (Raw JSON mode)")
        
        start_time = datetime.now()
        stats = {
            "start_time": start_time.isoformat(),
            "chapters_processed": 0,
            "images_extracted": 0,
            "failed_chapters": [],
            "output_files": []
        }
        
        try:
            # Discover all PDF files
            pdf_files = self.discover_pdf_files()
            
            if not pdf_files:
                logger.error("❌ No PDF files found to process")
                return stats
            
            # Process each chapter individually
            for chapter_id, pdf_path in pdf_files:
                try:
                    logger.info(f"\n{'='*60}")
                    logger.info(f"📄 Processing Chapter: {chapter_id}")
                    logger.info(f"📁 Source: {pdf_path.name}")
                    logger.info(f"{'='*60}")
                    
                    # Check if already processed
                    if self.progress.is_completed(str(pdf_path)):
                        logger.info(f"⏭️ Skipping already processed: {chapter_id}")
                        continue
                    
                    if self.progress.is_failed(str(pdf_path)):
                        logger.info(f"⚠️ Skipping previously failed: {chapter_id}")
                        continue
                    
                    # Extract chapter content
                    chapter_data = self.extract_single_chapter(chapter_id, pdf_path)
                    
                    if chapter_data:
                        # Save JSON file
                        output_file = self.save_chapter_json(chapter_data)
                        stats["output_files"].append(str(output_file))
                        stats["chapters_processed"] += 1
                        
                        # Count images
                        images_count = len(chapter_data.get('image_context', []))
                        stats["images_extracted"] += images_count
                        
                        # Mark as completed
                        self.progress.mark_completed(str(pdf_path))
                        
                        logger.info(f"✅ Chapter {chapter_id} completed successfully")
                        logger.info(f"   📊 {images_count} images, JSON saved")
                        
                    else:
                        stats["failed_chapters"].append(chapter_id)
                        self.progress.mark_failed(str(pdf_path))
                        logger.error(f"❌ Chapter {chapter_id} failed")
                    
                    # Force garbage collection to manage memory
                    gc.collect()
                        
                except Exception as e:
                    logger.error(f"Error processing chapter {chapter_id}: {e}")
                    logger.error(traceback.format_exc())
                    stats["failed_chapters"].append(chapter_id)
                    self.progress.mark_failed(str(pdf_path))
            
            # Final statistics
            end_time = datetime.now()
            duration = end_time - start_time
            
            stats.update({
                "end_time": end_time.isoformat(),
                "duration_seconds": duration.total_seconds(),
                "duration_formatted": str(duration)
            })
            
            # Print summary
            logger.info(f"\n{'='*60}")
            logger.info("📊 EXTRACTION SUMMARY")
            logger.info(f"{'='*60}")
            logger.info(f"✅ Chapters processed: {stats['chapters_processed']}")
            logger.info(f"🖼️ Images extracted: {stats['images_extracted']}")
            logger.info(f"❌ Failed chapters: {len(stats['failed_chapters'])}")
            logger.info(f"⏱️ Duration: {stats['duration_formatted']}")
            logger.info(f"📁 Output files: {len(stats['output_files'])}")
            
            if stats["failed_chapters"]:
                logger.error(f"Failed chapters: {', '.join(stats['failed_chapters'])}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Fatal error in extraction process: {e}")
            logger.error(traceback.format_exc())
            raise

def main():
    """Main execution function."""
    try:
        # Configuration
        config = ExtractionConfig()
        
        # Validate input directory exists
        if not os.path.exists(config.input_base_path):
            logger.error(f"❌ Input directory not found: {config.input_base_path}")
            logger.info("Please ensure the NIOS PDFs dataset is properly uploaded to Kaggle")
            sys.exit(1)
        
        # Initialize and run extractor
        extractor = NISODoclingExtractor(config)
        stats = extractor.run_extraction()
        
        # Save final statistics
        stats_file = Path("/kaggle/working/extraction_stats.json")
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"📊 Final statistics saved to: {stats_file}")
        
        if stats["chapters_processed"] > 0:
            logger.info("🎉 Extraction completed successfully!")
        else:
            logger.error("💥 No subjects were successfully processed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("⏹️ Extraction interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
