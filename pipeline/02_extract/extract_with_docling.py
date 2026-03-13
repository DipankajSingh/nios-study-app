#!/usr/bin/env python3
"""
NIOS Chapter Content Extractor using IBM Docling
=================================================

Extracts text, equations, tables, and images from NIOS chapter PDFs using IBM's Docling 
with schema compliance and complete image capture. Designed for Kaggle environment with
resume capability for processing large datasets.

Directory Structure Expected:
/kaggle/input/datasets/dipankaj/nios-chapter-pdfs/
├── class10/
│   ├── maths-10/
│   │   ├── Chapter 01.pdf
│   │   ├── Chapter 02.pdf
│   │   └── ...
│   └── science-10/
└── class12/
    ├── maths-12/
    └── physics-12/

Output: ExtractedSubject JSON files following pipeline schemas with linked images.
"""

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
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PDFPipelineOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

# Import pipeline schemas
sys.path.append('/kaggle/working')
try:
    from schemas import (
        Subject, Chapter, ExtractedChapter, ExtractedSubject, 
        ClassLevel, ContentBlockType
    )
except ImportError:
    # Fallback: define minimal schemas if import fails
    from enum import Enum
    from pydantic import BaseModel
    
    class ClassLevel(str, Enum):
        TEN = "10"
        TWELVE = "12"
    
    class Subject(BaseModel):
        id: str
        name: str
        class_level: ClassLevel
        code: str = ""
        description: str = ""
        icon: str = "📘"
        total_marks: int = 100
    
    class Chapter(BaseModel):
        id: str
        subject_id: str
        title: str
        order_index: int
        expected_weightage: int = 0
    
    class ExtractedChapter(BaseModel):
        chapter_id: str
        chapter_title: str
        order_index: int
        source_pdf: str
        markdown_text: str
        image_paths: List[str] = []
    
    class ExtractedSubject(BaseModel):
        subject: Subject
        extracted_at: str
        chapters: List[ExtractedChapter]

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
    output_base_path: str = "/kaggle/working/extracted"
    images_base_path: str = "/kaggle/working/images"
    resume_file: str = "/kaggle/working/extraction_progress.json"
    batch_size: int = 1  # Process one PDF at a time for memory efficiency
    max_image_size: int = 1024 * 1024 * 5  # 5MB max per image
    supported_image_formats: tuple = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')

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
    """Enhanced image extractor with multiple strategies for different docling versions."""
    
    def __init__(self, base_path: str, max_size: int):
        self.base_path = Path(base_path)
        self.max_size = max_size
        self.base_path.mkdir(parents=True, exist_ok=True)
        
    def extract_images_from_document(self, doc_result, chapter_id: str) -> List[str]:
        """Extract images from docling document with multiple strategies."""
        images_dir = self.base_path / chapter_id
        images_dir.mkdir(exist_ok=True)
        
        extracted_images = []
        
        try:
            # Strategy 1: Extract from document pictures
            if hasattr(doc_result.document, 'pictures') and doc_result.document.pictures:
                logger.info(f"Found {len(doc_result.document.pictures)} pictures in document")
                extracted_images.extend(self._extract_from_pictures(
                    doc_result.document.pictures, images_dir, chapter_id
                ))
            
            # Strategy 2: Extract from page-level content
            if hasattr(doc_result.document, 'pages'):
                for page_idx, page in enumerate(doc_result.document.pages):
                    if hasattr(page, 'images') and page.images:
                        extracted_images.extend(self._extract_from_page_images(
                            page.images, images_dir, chapter_id, page_idx
                        ))
            
            # Strategy 3: Check for alternative image containers
            extracted_images.extend(self._extract_alternative_formats(
                doc_result, images_dir, chapter_id
            ))
            
        except Exception as e:
            logger.error(f"Error extracting images for {chapter_id}: {e}")
            logger.error(traceback.format_exc())
        
        logger.info(f"Successfully extracted {len(extracted_images)} images for {chapter_id}")
        return extracted_images
    
    def _extract_from_pictures(self, pictures: List, images_dir: Path, chapter_id: str) -> List[str]:
        """Extract from document.pictures with multiple data format strategies."""
        extracted = []
        
        for i, pic_data in enumerate(pictures):
            try:
                image_saved = False
                image_path = images_dir / f"image_{i+1:03d}.png"
                
                # Strategy 1: Direct PIL image in top-level keys
                for key in ['image', 'pil_image', 'picture', 'img']:
                    if hasattr(pic_data, key):
                        img_obj = getattr(pic_data, key)
                        if self._save_pil_image(img_obj, image_path):
                            extracted.append(str(image_path))
                            image_saved = True
                            break
                
                if image_saved:
                    continue
                
                # Strategy 2: Check nested 'data' dictionary
                if hasattr(pic_data, 'data') and isinstance(pic_data.data, dict):
                    # Try PIL images in data dict
                    for key in ['image', 'pil_image', 'picture', 'content']:
                        if key in pic_data.data:
                            img_obj = pic_data.data[key]
                            if self._save_pil_image(img_obj, image_path):
                                extracted.append(str(image_path))
                                image_saved = True
                                break
                    
                    if not image_saved:
                        # Try base64/bytes content
                        if self._save_base64_or_bytes(pic_data.data, image_path):
                            extracted.append(str(image_path))
                            image_saved = True
                
                # Strategy 3: Try the entire pic_data as image
                if not image_saved:
                    if self._save_pil_image(pic_data, image_path):
                        extracted.append(str(image_path))
                        image_saved = True
                
                if not image_saved:
                    logger.warning(f"Could not extract image {i+1} from {chapter_id}")
                    logger.debug(f"pic_data type: {type(pic_data)}, attributes: {dir(pic_data)}")
                
            except Exception as e:
                logger.error(f"Error extracting picture {i+1} from {chapter_id}: {e}")
        
        return extracted
    
    def _extract_from_page_images(self, page_images: List, images_dir: Path, chapter_id: str, page_idx: int) -> List[str]:
        """Extract images from page-level image containers."""
        extracted = []
        
        for i, img_data in enumerate(page_images):
            try:
                image_path = images_dir / f"page_{page_idx+1}_image_{i+1:03d}.png"
                
                if self._save_pil_image(img_data, image_path):
                    extracted.append(str(image_path))
                elif hasattr(img_data, 'data') and self._save_base64_or_bytes(img_data.data, image_path):
                    extracted.append(str(image_path))
                else:
                    logger.warning(f"Could not extract page image {i+1} from page {page_idx+1} of {chapter_id}")
                    
            except Exception as e:
                logger.error(f"Error extracting page image {i+1} from page {page_idx+1} of {chapter_id}: {e}")
        
        return extracted
    
    def _extract_alternative_formats(self, doc_result, images_dir: Path, chapter_id: str) -> List[str]:
        """Extract from alternative image containers in the document."""
        extracted = []
        
        try:
            # Check for figures, diagrams, or other image containers
            for attr_name in ['figures', 'diagrams', 'media', 'attachments']:
                if hasattr(doc_result.document, attr_name):
                    items = getattr(doc_result.document, attr_name)
                    if items:
                        for i, item in enumerate(items):
                            try:
                                image_path = images_dir / f"{attr_name}_{i+1:03d}.png"
                                if self._save_pil_image(item, image_path):
                                    extracted.append(str(image_path))
                            except Exception as e:
                                logger.debug(f"Could not extract {attr_name} {i+1}: {e}")
        
        except Exception as e:
            logger.debug(f"Error in alternative image extraction: {e}")
        
        return extracted
    
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
    """Main extractor class for NIOS content using Docling."""
    
    def __init__(self, config: ExtractionConfig):
        self.config = config
        self.progress = ProgressTracker(config.resume_file)
        self.image_extractor = ImageExtractor(config.images_base_path, config.max_image_size)
        
        # Setup output directories
        Path(config.output_base_path).mkdir(parents=True, exist_ok=True)
        Path(config.images_base_path).mkdir(parents=True, exist_ok=True)
        
        # Configure Docling with optimal settings for NIOS PDFs
        self.converter = self._setup_docling_converter()
        
        logger.info("📚 NIOS Docling Extractor initialized")
        logger.info(f"Input path: {config.input_base_path}")
        logger.info(f"Output path: {config.output_base_path}")
    
    def _setup_docling_converter(self) -> DocumentConverter:
        """Configure Docling converter with optimal settings for academic PDFs."""
        try:
            # Configure pipeline for comprehensive extraction
            pdf_options = PDFPipelineOptions()
            pdf_options.images_scale = 2.0  # Higher quality image extraction
            pdf_options.generate_page_images = True
            pdf_options.generate_picture_images = True
            
            # Initialize converter with optimal settings
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: pdf_options,
                }
            )
            
            logger.info("✓ Docling converter configured successfully")
            return converter
            
        except Exception as e:
            logger.warning(f"Could not configure advanced options: {e}")
            # Fallback to basic converter
            return DocumentConverter()
    
    def discover_pdf_files(self) -> Dict[str, List[Tuple[str, Path]]]:
        """Discover all PDF files organized by subject."""
        input_path = Path(self.config.input_base_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input directory not found: {input_path}")
        
        subjects = {}
        
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
                pdf_files = []
                
                # Find all PDF files in subject directory
                for pdf_file in subject_dir.glob("*.pdf"):
                    pdf_files.append((subject_id, pdf_file))
                
                if pdf_files:
                    # Sort by chapter number if possible
                    pdf_files.sort(key=lambda x: self._extract_chapter_number(x[1].name))
                    subjects[subject_id] = pdf_files
                    logger.info(f"Found {len(pdf_files)} PDFs for {subject_id}")
        
        total_pdfs = sum(len(files) for files in subjects.values())
        logger.info(f"📊 Discovered {len(subjects)} subjects with {total_pdfs} total PDFs")
        
        return subjects
    
    def _extract_chapter_number(self, filename: str) -> int:
        """Extract chapter number from filename for sorting."""
        import re
        match = re.search(r'[Cc]hapter\s*(\d+)', filename)
        return int(match.group(1)) if match else 999
    
    def extract_subject(self, subject_id: str, pdf_files: List[Tuple[str, Path]]) -> Optional[ExtractedSubject]:
        """Extract content from all PDFs in a subject."""
        logger.info(f"🔄 Processing subject: {subject_id} ({len(pdf_files)} chapters)")
        
        # Create subject model
        class_level = ClassLevel.TEN if "10" in subject_id else ClassLevel.TWELVE
        subject = Subject(
            id=subject_id,
            name=subject_id.replace("-", " ").title(),
            class_level=class_level
        )
        
        extracted_chapters = []
        successful_extractions = 0
        
        for i, (_, pdf_path) in enumerate(pdf_files):
            try:
                # Check if already processed
                if self.progress.is_completed(str(pdf_path)):
                    logger.info(f"⏭️ Skipping already processed: {pdf_path.name}")
                    continue
                
                if self.progress.is_failed(str(pdf_path)):
                    logger.info(f"⚠️ Skipping previously failed: {pdf_path.name}")
                    continue
                
                logger.info(f"📄 Extracting chapter {i+1}/{len(pdf_files)}: {pdf_path.name}")
                
                # Extract single chapter
                extracted_chapter = self._extract_single_chapter(
                    pdf_path, subject_id, i + 1
                )
                
                if extracted_chapter:
                    extracted_chapters.append(extracted_chapter)
                    self.progress.mark_completed(str(pdf_path))
                    successful_extractions += 1
                    logger.info(f"✅ Successfully extracted: {pdf_path.name}")
                else:
                    self.progress.mark_failed(str(pdf_path))
                    logger.error(f"❌ Failed to extract: {pdf_path.name}")
                
                # Force garbage collection to manage memory
                gc.collect()
                
            except Exception as e:
                logger.error(f"Error processing {pdf_path}: {e}")
                logger.error(traceback.format_exc())
                self.progress.mark_failed(str(pdf_path))
        
        if not extracted_chapters:
            logger.warning(f"No chapters successfully extracted for {subject_id}")
            return None
        
        # Create extracted subject
        extracted_subject = ExtractedSubject(
            subject=subject,
            extracted_at=datetime.now().isoformat(),
            chapters=extracted_chapters
        )
        
        logger.info(f"✨ Subject {subject_id} extraction complete: {successful_extractions}/{len(pdf_files)} chapters")
        return extracted_subject
    
    def _extract_single_chapter(self, pdf_path: Path, subject_id: str, chapter_order: int) -> Optional[ExtractedChapter]:
        """Extract content from a single PDF chapter."""
        try:
            # Generate chapter ID
            chapter_id = f"{subject_id}-ch{chapter_order:02d}"
            
            logger.info(f"🔍 Processing PDF: {pdf_path}")
            
            # Convert PDF using Docling
            doc_result = self.converter.convert(str(pdf_path))
            
            if not doc_result or not doc_result.document:
                logger.error(f"Docling failed to process: {pdf_path}")
                return None
            
            # Extract text content as markdown
            markdown_text = doc_result.document.export_to_markdown()
            
            if not markdown_text.strip():
                logger.warning(f"No text content extracted from: {pdf_path}")
                markdown_text = f"# {pdf_path.stem}\n\n*No text content could be extracted from this PDF.*"
            
            # Extract images
            image_paths = self.image_extractor.extract_images_from_document(
                doc_result, chapter_id
            )
            
            # Convert absolute paths to relative paths for portability
            relative_image_paths = [
                str(Path(img_path).relative_to(Path(self.config.images_base_path)))
                for img_path in image_paths
            ]
            
            # Create extracted chapter
            extracted_chapter = ExtractedChapter(
                chapter_id=chapter_id,
                chapter_title=pdf_path.stem,
                order_index=chapter_order,
                source_pdf=str(pdf_path),
                markdown_text=markdown_text,
                image_paths=relative_image_paths
            )
            
            # Log extraction statistics
            text_length = len(markdown_text)
            image_count = len(relative_image_paths)
            logger.info(f"📊 Extracted: {text_length:,} chars text, {image_count} images")
            
            return extracted_chapter
            
        except Exception as e:
            logger.error(f"Error extracting chapter from {pdf_path}: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def save_extracted_subject(self, extracted_subject: ExtractedSubject) -> Path:
        """Save extracted subject data as JSON."""
        output_file = Path(self.config.output_base_path) / f"{extracted_subject.subject.id}.json"
        
        try:
            # Convert to dict and save as JSON
            subject_data = extracted_subject.model_dump(indent=2)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(subject_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Saved extracted subject: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Error saving extracted subject: {e}")
            raise
    
    def run_extraction(self) -> Dict[str, Any]:
        """Run the complete extraction process."""
        logger.info("🚀 Starting NIOS content extraction with Docling")
        
        start_time = datetime.now()
        stats = {
            "start_time": start_time.isoformat(),
            "subjects_processed": 0,
            "chapters_extracted": 0,
            "images_extracted": 0,
            "failed_subjects": [],
            "output_files": []
        }
        
        try:
            # Discover all PDF files
            subjects = self.discover_pdf_files()
            
            if not subjects:
                logger.error("❌ No PDF files found to process")
                return stats
            
            # Process each subject
            for subject_id, pdf_files in subjects.items():
                try:
                    logger.info(f"\n{'='*60}")
                    logger.info(f"📚 Processing Subject: {subject_id}")
                    logger.info(f"{'='*60}")
                    
                    extracted_subject = self.extract_subject(subject_id, pdf_files)
                    
                    if extracted_subject:
                        # Save extracted data
                        output_file = self.save_extracted_subject(extracted_subject)
                        stats["output_files"].append(str(output_file))
                        stats["subjects_processed"] += 1
                        stats["chapters_extracted"] += len(extracted_subject.chapters)
                        
                        # Count images
                        total_images = sum(
                            len(chapter.image_paths) 
                            for chapter in extracted_subject.chapters
                        )
                        stats["images_extracted"] += total_images
                        
                        logger.info(f"✅ Subject {subject_id} completed successfully")
                    else:
                        stats["failed_subjects"].append(subject_id)
                        logger.error(f"❌ Subject {subject_id} failed")
                        
                except Exception as e:
                    logger.error(f"Error processing subject {subject_id}: {e}")
                    stats["failed_subjects"].append(subject_id)
            
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
            logger.info(f"✅ Subjects processed: {stats['subjects_processed']}")
            logger.info(f"📄 Chapters extracted: {stats['chapters_extracted']}")
            logger.info(f"🖼️ Images extracted: {stats['images_extracted']}")
            logger.info(f"❌ Failed subjects: {len(stats['failed_subjects'])}")
            logger.info(f"⏱️ Duration: {stats['duration_formatted']}")
            logger.info(f"📁 Output files: {len(stats['output_files'])}")
            
            if stats["failed_subjects"]:
                logger.error(f"Failed subjects: {', '.join(stats['failed_subjects'])}")
            
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
        
        if stats["subjects_processed"] > 0:
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