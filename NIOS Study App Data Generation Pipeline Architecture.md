# NIOS Study App: Data Generation Pipeline Architecture

**Goal:** Convert raw, complex NIOS PDFs (Math, CS, Science) into verified, multimodal JSON data, constrained to a 1000 INR budget.

## Pipeline Overview

We are splitting the workload to optimize costs:

1. **Heavy Lifting (Cost $0):** Local machine runs `docling` to crack the PDFs, parse multi-column layouts, convert math to LaTeX, crop images, and output clean Markdown.
2. **Structuring (Cost ~$2):** DeepSeek V3 API takes the Markdown and formats it into our strict Pydantic/JSON schema.
3. **Verification (Cost $0):** Local Python script checks for hallucinations using the `exact_source_quote` rule.
4. **Solving PYQs (Cost ~$10):** Claude 3.7 Sonnet reads Past Year Questions and generates step-by-step LaTeX solutions.

---

## Step 1: Environment Setup

Do not try to run this on a Raspberry Pi. You need a standard Windows/Mac/Linux machine.

Create a virtual environment and install the exact dependencies:

Bash

`python -m venv nios_env
source nios_env/bin/activate  # On Windows: nios_env\Scripts\activate

# Install docling with VLM (Vision Language Model) support for diagrams/math
pip install "docling[vlm]" pydantic python-dotenv requests`

Set up a `.env` file in your project root:

Code snippet

`DEEPSEEK_API_KEY=your_deepseek_key_here
CLAUDE_API_KEY=your_anthropic_key_here`

---

## Step 2: Local Multimodal Extraction (The Docling Script)

This script reads a NIOS PDF, extracts all the text/math, and saves all diagrams as standalone images.

**File: `1_extract_pdf.py`**

Python

`import os
from pathlib import Path
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat

def extract_nios_pdf(pdf_path: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    
    # Configure Docling to aggressively process images and math
    pipeline_options = PdfPipelineOptions()
    pipeline_options.generate_picture_images = True
    pipeline_options.do_formula_enrichment = True # Converts math to LaTeX
    
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfPipelineOptions(pipeline_options=pipeline_options)}
    )
    
    print(f"Cracking PDF: {pdf_path}...")
    result = converter.convert(pdf_path)
    
    # 1. Save the Markdown
    md_output = result.document.export_to_markdown()
    md_filename = os.path.join(output_dir, Path(pdf_path).stem + ".md")
    with open(md_filename, "w", encoding="utf-8") as f:
        f.write(md_output)
        
    # 2. Save the extracted images locally 
    # (Next step for your dev: Write a function to push these to Cloudflare R2)
    img_dir = os.path.join(output_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    
    for element in result.document.pictures:
        if element.image:
            img_path = os.path.join(img_dir, f"img_{element.id}.png")
            element.image.save(img_path)

    print(f"Done! Markdown saved to {md_filename}")

# Run it
extract_nios_pdf("raw_pdfs/maths-12-book1.pdf", "processed_data/maths-12")`

---

## Step 3: Pydantic + API Structuring Engine

Docling has a native `DocumentExtractor`. We will define our `ContentBlock` schema using Pydantic, and use an API to map the Markdown into that schema.

*Note for your dev: You will need to write a custom wrapper or use LiteLLM to route Docling's extractor to the DeepSeek V3 API to save money.*

**File: `2_structure_data.py`**

Python

`from pydantic import BaseModel, Field
from typing import Optional
import json

# This is the exact schema we designed earlier
class ContentBlock(BaseModel):
    topic_name: str = Field(description="The specific topic this block belongs to")
    type: str = Field(description="Must be CONCEPT, FORMULA, DIAGRAM, CODE_SNIPPET, or COMMON_MISTAKE")
    content_text: Optional[str] = Field(description="The student-friendly notes, formatted in Markdown/LaTeX")
    code_content: Optional[str] = Field(description="Exact code block if applicable")
    
    # THE ANTI-HALLUCINATION LAYER
    exact_source_quote: str = Field(description="You MUST copy/paste the exact verbatim sentence from the source text that proves this concept.")

# The Prompt you will send to DeepSeek V3 along with chunks of the Markdown
SYSTEM_PROMPT = """
You are an expert data extractor. Read the provided NIOS study material chunk. 
Output a JSON array of ContentBlock objects. 
CRITICAL RULE: Do not invent facts. Every single block must include an `exact_source_quote` taken verbatim from the text. 
If it is a math formula, wrap it in standard LaTeX $ delimiters.
"""

# Your dev writes the API call to DeepSeek here, passing the SYSTEM_PROMPT 
# and a chunk of the Markdown from Step 2.`

---

## Step 4: The Local Verification Script (Crucial)

Do not push the DeepSeek JSON straight to the database. Run it through this script to catch API lies.

**File: `3_verify_data.py`**

Python

`import json

def verify_extracted_blocks(json_file_path: str, original_md_path: str):
    with open(original_md_path, 'r', encoding='utf-8') as f:
        source_text = f.read()
        
    with open(json_file_path, 'r', encoding='utf-8') as f:
        blocks = json.load(f)
        
    verified_blocks = []
    
    for block in blocks:
        quote = block.get("exact_source_quote", "")
        
        # Simple fuzzy/exact match
        if quote and quote in source_text:
            block["is_verified"] = True
            verified_blocks.append(block)
        else:
            print(f"❌ HALLUCINATION DETECTED! Dropping block for topic: {block.get('topic_name')}")
            print(f"Fake Quote: {quote}\n")
            
    # Save the verified blocks to a new file ready for Cloudflare D1
    with open("verified_database_seed.json", "w") as f:
        json.dump(verified_blocks, f, indent=2)

# Run it
verify_extracted_blocks("deepseek_output.json", "processed_data/maths-12/maths-12-book1.md")`

---

## Step 5: The High-Reasoning PYQ Solver

For past year questions, you isolate the question text and send it to **Claude 3.7 Sonnet**.

**The Claude Prompt constraint:**

> "You are a strict NIOS examiner. Solve the following Past Year Question.
> 
> 1. Provide a step-by-step `solution_text` using LaTeX for all math.
> 2. Determine the `difficulty` (EASY/MEDIUM/HARD).
> 3. Provide a `common_errors_text` explaining where a student is most likely to lose marks on this specific question."