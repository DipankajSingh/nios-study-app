import re

with open("pipeline/03_structure/structure_content.py", "r") as f:
    code = f.read()

chunk_docling_blocks_code = """
def chunk_docling_blocks(doc_dict: dict, target_size: int = CHUNK_SIZE) -> list[str]:
    \"\"\"Group docling JSON blocks semantically.
    
    Docling structure is a sequence of `texts` and `pictures`.
    We extract the text representation and group them, prioritizing heading splits.
    \"\"\"
    chunks = []
    current_chunk = []
    current_size = 0
    
    # Docling 2.0 export format
    items = doc_dict.get("texts", []) + doc_dict.get("pictures", []) + doc_dict.get("tables", [])
    
    # Sort items by their sequence index to maintain document order
    # Some docling versions store it explicitly in prov or ID
    # For robust parsing, we can just use the flat text representation
    # if it's available, otherwise we construct it.
    
    # Actually, docling's easiest chunking is via its rich text renderer
    # but since we already have the JSON, we need to extract from "texts" array.
    
    if not items:
        return []
        
    # Sort by document flow order if "id" or "prov" exist, otherwise rely on the array
    try:
        items.sort(key=lambda x: x.get("prov", [{}])[0].get("page_no", 0) * 10000 + x.get("prov", [{}])[0].get("bbox", [0, 0, 0, 0])[1])
    except:
        pass # Not fatal, fallback to whatever order they are in

    for b in items:
        # Check if it's an image
        if "image_filename" in b:
            text = f"[Image: <img src=\\"{b['image_filename']}\\" />]"
            btype = "Picture"
        else:
            text = b.get("text", "")
            btype = b.get("label", b.get("type", "unknown"))
            
        if not text:
            continue
            
        # Prioritize breaking at headings
        if btype in ("section_header", "title", "heading", "page_header") and current_size > target_size * 0.5:
            chunks.append("\\n\\n".join(current_chunk))
            current_chunk = []
            current_size = 0
            
        current_chunk.append(text)
        current_size += len(text)
        
        # Max chunk break
        if current_size >= target_size and btype in ("text", "paragraph", "list_item"):
            chunks.append("\\n\\n".join(current_chunk))
            current_chunk = []
            current_size = 0
            
    if current_chunk:
        chunks.append("\\n\\n".join(current_chunk))
        
    return [c for c in chunks if len(c) > 50]
"""

# Replace the chunk_marker_blocks with chunk_docling_blocks
code = re.sub(
    r'def chunk_marker_blocks\(.*?return \[c for c in chunks if len\(c\) > 50\].*?\n',
    chunk_docling_blocks_code + '\n',
    code,
    flags=re.DOTALL
)

# Replace 'blocks = data.get("blocks", [])' and 'chunks = chunk_marker_blocks(blocks)'
code = code.replace(
    'blocks = data.get("blocks", [])\n            chunks = chunk_marker_blocks(blocks)',
    'chunks = chunk_docling_blocks(data)'
)
code = code.replace(
    'chunks = chunk_marker_blocks(data.get("blocks", []))',
    'chunks = chunk_docling_blocks(data)'
)

with open("pipeline/03_structure/structure_content.py", "w") as f:
    f.write(code)

print("Updated 03_structure to use Docling JSON structure.")
