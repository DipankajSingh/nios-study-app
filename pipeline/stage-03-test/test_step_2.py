import fastdup
import pandas as pd
import json
import os
import shutil

# --- CONFIG ---
MASTER_IMAGE_DIR = "./master_image_pool"
FASTDUP_WORK_DIR = "./fastdup_workdir"
REVIEW_MANIFEST_FILE = "./cluster_review_manifest.json"
OUTPUT_HTML = "./manual_review.html"

def run_clustering_and_gallery():
    if not os.path.exists(MASTER_IMAGE_DIR) or not os.listdir(MASTER_IMAGE_DIR):
        print(f"Error: {MASTER_IMAGE_DIR} is empty or missing. Run Stage 1 first.")
        return

    print("Initializing fastdup engine...")
    
    # Wipe old work directory
    if os.path.exists(FASTDUP_WORK_DIR):
        shutil.rmtree(FASTDUP_WORK_DIR)
        
    fd = fastdup.create(input_dir=MASTER_IMAGE_DIR, work_dir=FASTDUP_WORK_DIR)
    
    print("Running perceptual analysis with strict threshold...")
    # CRITICAL: threshold=0.95 prevents false positives
    fd.run(overwrite=True, threshold=0.75)
    
    print("Extracting cluster data...")
    try:
        clusters_df = fd.connected_components()[0]    
    except Exception as e:
        print(f"Failed to extract components: {e}")
        return

    cluster_counts = clusters_df['component_id'].value_counts()
    duplicate_components = cluster_counts[cluster_counts > 1].index
    duplicates_df = clusters_df[clusters_df['component_id'].isin(duplicate_components)]

    manifest = {}
    
    # 1. BUILD THE JSON MANIFEST
    for comp_id in duplicate_components:
        cluster_name = f"Cluster_{comp_id}"
        cluster_files = duplicates_df[duplicates_df['component_id'] == comp_id]['filename'].tolist()
        clean_files = [os.path.basename(f) for f in cluster_files]
        
        manifest[cluster_name] = {
            "sample_image": clean_files[0],
            "total_images_in_cluster": len(clean_files),
            "action": "keep",      
            "reason": "",          
            "all_files": clean_files 
        }

    with open(REVIEW_MANIFEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=4)

    # 2. BUILD THE NATIVE HTML GALLERY
    print("Generating visual review gallery...")
    html_content = """
    <html>
    <head>
        <style>
            body { font-family: sans-serif; background: #1a1a1a; color: white; padding: 20px; }
            .cluster { border: 2px solid #444; margin-bottom: 40px; padding: 15px; border-radius: 8px; }
            .cluster-title { font-size: 24px; color: #00ffcc; margin-bottom: 10px; }
            .image-grid { display: flex; flex-wrap: wrap; gap: 10px; }
            .img-container { text-align: center; background: #333; padding: 5px; border-radius: 4px; }
            img { max-width: 200px; max-height: 200px; display: block; margin-bottom: 5px; }
            .filename { font-size: 10px; color: #bbb; max-width: 200px; word-wrap: break-word; }
        </style>
    </head>
    <body>
        <h1>Textbook Image Cluster Review</h1>
        <p>Review the groups below. If a group contains garbage (logos/lines), open <code>cluster_review_manifest.json</code> and mark it as <b>'remove'</b>.</p>
    """

    for cluster_id, data in manifest.items():
        html_content += f'<div class="cluster"><div class="cluster-title">{cluster_id} ({data["total_images_in_cluster"]} images)</div>'
        html_content += '<div class="image-grid">'
        
        for img_name in data["all_files"]:
            img_path = os.path.join(MASTER_IMAGE_DIR, img_name)
            html_content += f"""
            <div class="img-container">
                <img src="{img_path}">
                <div class="filename">{img_name}</div>
            </div>"""
            
        html_content += "</div></div>"

    html_content += "</body></html>"

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html_content)

    unique_images_count = len(clusters_df) - len(duplicates_df)
    
    print("\n--- STAGE 2 COMPLETE ---")
    print(f"Total Images Analyzed: {len(clusters_df)}")
    print(f"Unique Images (Automatically Kept): {unique_images_count}")
    print(f"Duplicate Clusters Found: {len(manifest)}")
    print(f"1. Review Manifest saved to: {REVIEW_MANIFEST_FILE}")
    print(f"2. Visual Gallery saved to: {OUTPUT_HTML}")
    print("ACTION: Open manual_review.html in your browser to verify.")

if __name__ == "__main__":
    run_clustering_and_gallery()