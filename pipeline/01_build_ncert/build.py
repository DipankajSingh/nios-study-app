import os
import json
import collections
import uuid
from datasets import load_dataset

def generate_id():
    return uuid.uuid4().hex[:8]

def run():
    print("Loading ParthKadam2003/NCERT_Dataset from HuggingFace...")
    ds = load_dataset("ParthKadam2003/NCERT_Dataset", split="train")
    
    subjects_map = {}
    chapters_map = {}
    topics_map = {}
    
    out_subjects = []
    out_chapters = []
    out_topics = []
    out_topic_contents = []
    out_pyqs = []
    out_pyq_explanations = []

    print(f"Processing {len(ds)} rows...")

    limit_counter = 0
    for row in ds:
        # Prevent Cloudflare Worker 1MB limit crash by restricting dataset size for MVP
        if limit_counter >= 3000:
            break

        subj_name = row.get("subject", "General")
        grade = str(row.get("grade", "12"))
        
        if grade != "12":
            continue
        if "math" not in subj_name.lower() and "physics" not in subj_name.lower() and "chemistry" not in subj_name.lower():
            continue
            
        limit_counter += 1
        
        subject_id = f"{subj_name.replace(' ', '-').lower()}-{grade}"
        
        # 1. Subject
        if subject_id not in subjects_map:
            subjects_map[subject_id] = True
            out_subjects.append({
                "id": subject_id,
                "name": subj_name,
                "classLevel": "12" if grade == "12" else "10",
                "description": f"NCERT {subj_name} for Class {grade}",
                "icon": "📘",
                "totalMarks": 100
            })
            
            # Single synthetic Chapter per subject (since the dataset lacks chapters)
            chapter_id = f"{subject_id}-ch01"
            chapters_map[subject_id] = chapter_id
            out_chapters.append({
                "id": chapter_id,
                "subjectId": subject_id,
                "title": f"All {subj_name} Concepts",
                "orderIndex": 1
            })

        if subject_id not in chapters_map:
             continue
        chapter_id = chapters_map[subject_id]
        
        # 2. Topic
        topic_title = str(row.get("Topic", "General Topic")).strip()
        topic_key = f"{subject_id}-{topic_title}"
        
        if topic_key not in topics_map:
            topic_id = f"{subject_id}-t{len(topics_map)}"
            topics_map[topic_key] = topic_id
            
            try:
                est_time = int(row.get("EstimatedTime", 15))
            except:
                est_time = 15

            out_topics.append({
                "id": topic_id,
                "chapterId": chapter_id,
                "title": topic_title,
                "orderIndex": len(topics_map),
                "highYieldScore": 50,
                "estMinutes": est_time
            })
            
            explanation = str(row.get("Explanation", ""))
            bullets = [s.strip() + "." for s in explanation.split(".") if len(s.strip()) > 5]
            if not bullets:
                bullets = [topic_title]
                
            out_topic_contents.append({
                "id": f"tc-{topic_id}",
                "topicId": topic_id,
                "lang": "en",
                "summaryBullets": bullets[:5], # Keep max 5 bullets
                "whyImportant": str(row.get("Prerequisites", "Essential NCERT concept")),
                "commonMistakes": [] # Non-AI format
            })
            
        topic_id = topics_map[topic_key]
        
        # 3. PYQ (Question)
        pyq_id = f"pyq-{generate_id()}"
        diff_str = str(row.get("Difficulty", "Medium")).lower()
        if diff_str not in ["easy", "medium", "hard"]:
            diff_str = "medium"
            
        out_pyqs.append({
            "id": pyq_id,
            "subjectId": subject_id,
            "topicId": topic_id,
            "year": "2024",
            "session": "March",
            "questionText": str(row.get("Question", "")),
            "marks": 5,
            "difficulty": diff_str,
            "frequencyScore": 5,
            "questionType": "short"
        })
        
        # 4. PYQ Explanation
        ans = str(row.get("Answer", ""))
        out_pyq_explanations.append({
            "id": f"exp-{pyq_id}",
            "pyqId": pyq_id,
            "lang": "en",
            "steps": [ans],
            "hints": [],
            "answer": ans,
            "commonErrors": ""
        })

    # Output to backend
    out_path = "/home/dipankaj/Desktop/nios-study-app/backend/src/data/generated.ts"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
    def ts_export(name, data):
        return f"export const {name} = {json.dumps(data, indent=2)};\n"
        
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("// AUTO-GENERATED from NCERT HuggingFace Dataset\n")
        f.write(ts_export("subjects", out_subjects))
        f.write(ts_export("chapters", out_chapters))
        f.write(ts_export("topics", out_topics))
        f.write(ts_export("topicContents", out_topic_contents))
        f.write(ts_export("pyqs", out_pyqs))
        f.write(ts_export("pyqExplanations", out_pyq_explanations))
        
    print(f"Generated TS arrays to {out_path}")

if __name__ == "__main__":
    run()
