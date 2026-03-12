with open("pipeline/03_structure/structure_content.py", "r") as f:
    code = f.read()

chunk_marker_blocks = """
def chunk_marker_blocks(blocks: list[dict], target_size: int = CHUNK_SIZE) -> list[str]:
    chunks = []
    current_chunk = []
    current_size = 0
    
    for b in blocks:
        btype = b.get("block_type", b.get("type", "unknown"))
        text = b.get("html", b.get("text", ""))
        
        if btype in ("Section-header", "Title", "Heading") and current_size > target_size * 0.5:
            chunks.append("\\n\\n".join(current_chunk))
            current_chunk = []
            current_size = 0
            
        current_chunk.append(text)
        current_size += len(text)
        
        if current_size >= target_size and btype in ("Text", "List-item", "Paragraph"):
            chunks.append("\\n\\n".join(current_chunk))
            current_chunk = []
            current_size = 0
            
    if current_chunk:
        chunks.append("\\n\\n".join(current_chunk))
        
    return [c for c in chunks if len(c) > 50]
"""

old_chunk_text_end = "    return [c for c in chunks if len(c) > 50]  # Skip tiny fragments"
code = code.replace(old_chunk_text_end, old_chunk_text_end + "\n\n" + chunk_marker_blocks)

old_process = """def process_chapter(
    md_file: Path,
    subject_cfg: dict,
    subject_id: str,
    chapter_index: int,
) -> StructuredChapter | None:
    \"\"\"Process one chapter markdown file → StructuredChapter.\"\"\"
    md_text = md_file.read_text(encoding="utf-8")
    if len(md_text) < 100:
        print(f"    ⏭️  Skipping {md_file.name} (too short: {len(md_text)} chars)")
        return None

    pdf_name = md_file.stem  # e.g. "01_311_Maths_Eng_Lesson1"
    chunks = chunk_text(md_text)
    print(f"    �� {md_file.name}: {len(md_text)} chars → {len(chunks)} chunks")"""

new_process = """def process_chapter(
    file_path: Path,
    subject_cfg: dict,
    subject_id: str,
    chapter_index: int,
) -> StructuredChapter | None:
    \"\"\"Process one chapter file (JSON or MD) → StructuredChapter.\"\"\"
    text_content = file_path.read_text(encoding="utf-8")
    
    if file_path.suffix == ".json":
        try:
            data = json.loads(text_content)
            blocks = data.get("blocks", [])
            chunks = chunk_marker_blocks(blocks)
        except Exception as e:
            print(f"    ❌ Failed to parse JSON {file_path.name}: {e}")
            return None
    else:
        chunks = chunk_text(text_content)
        
    if not chunks:
        print(f"    ⏭️  Skipping {file_path.name} (no content chunks)")
        return None

    pdf_name = file_path.stem
    print(f"    📄 {file_path.name}: {len(chunks)} chunks")"""

code = code.replace(old_process, new_process)
code = code.replace("print(f\"    ⚠️  No topics extracted from {md_file.name}\")", "print(f\"    ⚠️  No topics extracted from {file_path.name}\")")

old_main = """    # Find markdown files
    md_files = sorted(extracted_dir.rglob("*.md"))
    if not md_files:
        print(f"❌ No .md files in {extracted_dir}")
        sys.exit(1)

    print(f"📚 Subject: {subject.name} ({args.subject})")
    print(f"📁 Source: {extracted_dir}")
    print(f"📄 Found {len(md_files)} markdown files")
    print(f"⏱️  Rate limit pause: {prov.get('pause', RATE_LIMIT_PAUSE)}s/req\\n")

    # Dry-run: just list files and sizes, then exit
    if args.dry_run:
        total_chunks = 0
        for md_file in md_files:
            text = md_file.read_text(encoding="utf-8")
            chunks = chunk_text(text)
            total_chunks += len(chunks)
            print(f"  📄 {md_file.relative_to(extracted_dir)}: {len(text):,} chars → {len(chunks)} chunks")
        est_time = total_chunks * prov.get("pause", RATE_LIMIT_PAUSE) + total_chunks * 5  # ~5s per API call
        print(f"\\n📊 Total: {len(md_files)} files, {total_chunks} chunks")"""

new_main = """    # Find JSON/markdown files
    source_files = sorted(extracted_dir.rglob("*.json"))
    if not source_files:
        source_files = sorted(extracted_dir.rglob("*.md"))
    source_files = [f for f in source_files if not f.name.startswith("_")]

    if not source_files:
        print(f"❌ No .json or .md files in {extracted_dir}")
        sys.exit(1)

    print(f"📚 Subject: {subject.name} ({args.subject})")
    print(f"📁 Source: {extracted_dir}")
    print(f"�� Found {len(source_files)} source files")
    print(f"⏱️  Rate limit pause: {prov.get('pause', RATE_LIMIT_PAUSE)}s/req\\n")

    if args.dry_run:
        total_chunks = 0
        for src_file in source_files:
            text = src_file.read_text(encoding="utf-8")
            if src_file.suffix == ".json":
                try:
                    data = json.loads(text)
                    chunks = chunk_marker_blocks(data.get("blocks", []))
                except Exception:
                    chunks = []
            else:
                chunks = chunk_text(text)
            total_chunks += len(chunks)
            print(f"  📄 {src_file.relative_to(extracted_dir)}: {len(text):,} chars → {len(chunks)} chunks")
        est_time = total_chunks * prov.get("pause", RATE_LIMIT_PAUSE) + total_chunks * 5
        print(f"\\n📊 Total: {len(source_files)} files, {total_chunks} chunks")"""

code = code.replace(old_main, new_main)

old_loop = """    for idx, md_file in enumerate(md_files, 1):
        ch_key = md_file.stem
        if ch_key in done_chapters:
            print(f"  ⏭️  [{idx}/{len(md_files)}] Skipping {md_file.name} (done)")
            continue

        print(f"\\n  📖 [{idx}/{len(md_files)}] Processing: {md_file.name}")
        chapter = process_chapter(md_file, subject_cfg, args.subject, idx)"""

new_loop = """    for idx, src_file in enumerate(source_files, 1):
        ch_key = src_file.stem
        if ch_key in done_chapters:
            print(f"  ⏭️  [{idx}/{len(source_files)}] Skipping {src_file.name} (done)")
            continue

        print(f"\\n  📖 [{idx}/{len(source_files)}] Processing: {src_file.name}")
        chapter = process_chapter(src_file, subject_cfg, args.subject, idx)"""
        
code = code.replace(old_loop, new_loop)

with open("pipeline/03_structure/structure_content.py", "w") as f:
    f.write(code)

