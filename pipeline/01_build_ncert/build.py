import os
import json
import collections
import uuid
from datasets import load_dataset

def generate_id():
    return uuid.uuid4().hex[:8]

def dollar_quote(s):
    """Safely escapes strings for PostgreSQL using dollar quotes."""
    clean_s = str(s).replace("$$", " ")
    return f"$${clean_s}$$"

def run():
    local_path = "/home/dipankaj/Desktop/nios-study-app/content/ncert_dataset.json"
    if os.path.exists(local_path):
        print(f"Loading local dataset from {local_path}...")
        ds = load_dataset("json", data_files=local_path, split="train")
    else:
        print("Downloading ParthKadam2003/NCERT_Dataset from HuggingFace...")
        ds = load_dataset("ParthKadam2003/NCERT_Dataset", split="train")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        ds.to_json(local_path)
    
    subjects_map = {}
    chapters_map = {}
    
    subs_values = []
    chaps_values = []
    topics_values = []
    tcontents_values = []
    pyqs_values = []
    exps_values = []

    print(f"Processing row mapping for Postgres...")
    
    topics_set = {}
    limit_counter = 0

    for row in ds:
        if limit_counter >= 10000:
            break

        subj_name = str(row.get("subject", "General")).strip()
        grade = str(row.get("grade", "12")).strip()
        
        if grade != "12": continue
        if subj_name.lower() not in ["physics", "chemistry", "mathematics"]: continue
            
        limit_counter += 1
        
        subject_id = f"{subj_name.lower()}-{grade}"
        
        # 1. Subject
        if subject_id not in subjects_map:
            subjects_map[subject_id] = True
            subs_values.append(f"({dollar_quote(subject_id)}, {dollar_quote(subj_name)}, {dollar_quote(grade)}, {dollar_quote('NCERT 12 ' + subj_name)}, {dollar_quote('📘')}, 100)")
            
            chapter_id = f"{subject_id}-ch01"
            chapters_map[subject_id] = chapter_id
            chaps_values.append(f"({dollar_quote(chapter_id)}, {dollar_quote(subject_id)}, {dollar_quote('All ' + subj_name + ' Concepts')}, 1)")

        if subject_id not in chapters_map: continue
        chapter_id = chapters_map[subject_id]
        
        # 2. Topic
        topic_title = str(row.get("Topic", "General Topic")).strip()
        topic_key = f"{subject_id}-{topic_title}"
        
        if topic_key not in topics_set:
            topic_id = f"{subject_id}-t{len(topics_set)}"
            topics_set[topic_key] = topic_id
            
            try: est_time = int(row.get("EstimatedTime", 15))
            except: est_time = 15
            
            # Parse prerequisites into an array of search terms
            raw_prereq = str(row.get("Prerequisites", ""))
            prereq_list = [p.strip() for p in raw_prereq.replace(";", ",").replace(" and ", ",").split(",") if len(p.strip()) > 2]
            prereq_terms = dollar_quote("{" + ",".join([f'"{p}"' for p in prereq_list]) + "}") if prereq_list else "DEFAULT"
            
            topics_values.append(f"({dollar_quote(topic_id)}, {dollar_quote(chapter_id)}, {dollar_quote(topic_title)}, {len(topics_set)}, DEFAULT, {prereq_terms}, 50, {est_time})")
            
            explanation = str(row.get("Explanation", ""))
            bullets = [s.strip() + "." for s in explanation.split(".") if len(s.strip()) > 5][:5]
            if not bullets: bullets = [topic_title]
            
            bullets_json = dollar_quote(json.dumps(bullets))
            empty_json = dollar_quote(json.dumps([]))
            why_imp = dollar_quote(str(row.get("Prerequisites", "Essential NCERT concept")))
            
            tcontents_values.append(f"({dollar_quote('tc-'+topic_id)}, {dollar_quote(topic_id)}, 'en', {bullets_json}::jsonb, {why_imp}, {empty_json}::jsonb)")
        
        topic_id = topics_set.get(topic_key)
        if not topic_id: continue
            
        # 3. PYQ (Question)
        pyq_id = f"pyq-{generate_id()}"
        diff_str = str(row.get("Difficulty", "Medium")).lower()
        if diff_str not in ["easy", "medium", "hard"]: diff_str = "medium"
        q_text = dollar_quote(str(row.get("Question", "")))
        
        pyqs_values.append(f"({dollar_quote(pyq_id)}, {dollar_quote(subject_id)}, {dollar_quote(topic_id)}, '2024', 'March', {q_text}, 5, {dollar_quote(diff_str)}, 5, 'short')")
        
        # 4. PYQ Explanation
        ans = str(row.get("Answer", ""))
        ans_quoted = dollar_quote(ans)
        steps_json = dollar_quote(json.dumps([ans]))
        empty_json = dollar_quote(json.dumps([]))
        
        exps_values.append(f"({dollar_quote('exp-'+pyq_id)}, {dollar_quote(pyq_id)}, 'en', {steps_json}::jsonb, {empty_json}::jsonb, {ans_quoted}, {dollar_quote('')})")

    out_path = "/home/dipankaj/Desktop/nios-study-app/supabase/seed.sql"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("-- AUTO-GENERATED NCERT SEED FILE FOR SUPABASE\n\n")
        
        if subs_values:
            f.write("INSERT INTO subjects (id, name, class_level, description, icon, total_marks) VALUES\n")
            f.write(",\n".join(subs_values) + ";\n\n")
            
        if chaps_values:
            f.write("INSERT INTO chapters (id, subject_id, title, order_index) VALUES\n")
            f.write(",\n".join(chaps_values) + ";\n\n")
            
        if topics_values:
            f.write("INSERT INTO topics (id, chapter_id, title, order_index, prerequisite_topic_ids, prerequisite_search_terms, high_yield_score, est_minutes) VALUES\n")
            f.write(",\n".join(topics_values) + ";\n\n")
            
        if tcontents_values:
            f.write("INSERT INTO topic_contents (id, topic_id, lang, summary_bullets, why_important, common_mistakes) VALUES\n")
            f.write(",\n".join(tcontents_values) + ";\n\n")
            
        if pyqs_values:
            f.write("INSERT INTO pyqs (id, subject_id, topic_id, year, session, question_text, marks, difficulty, frequency_score, question_type) VALUES\n")
            f.write(",\n".join(pyqs_values) + ";\n\n")
            
        if exps_values:
            f.write("INSERT INTO pyq_explanations (id, pyq_id, lang, steps, hints, answer, common_errors) VALUES\n")
            f.write(",\n".join(exps_values) + ";\n\n")
            
    print(f"Successfully generated 10,000+ row SQL seed at {out_path}")

if __name__ == "__main__":
    run()
