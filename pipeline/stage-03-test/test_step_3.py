import json
import os

# --- CONFIG ---
INVENTORY_FILE = "./image_inventory.json"
REVIEW_MANIFEST_FILE = "./cluster_review_manifest.json"
MASTER_IMAGE_DIR = "./master_image_pool"
# The base URL where these images will eventually live
CLOUDFLARE_BASE_URL = "https://test-app.cloudflare.com/"

def run_stage3_purge():
    if not os.path.exists(INVENTORY_FILE) or not os.path.exists(REVIEW_MANIFEST_FILE):
        print("Error: Missing inventory or manifest. Cannot proceed.")
        return

    print("Loading inventory and human-reviewed manifest...")
    with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
        inventory = json.load(f)

    with open(REVIEW_MANIFEST_FILE, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    # 1. Map exactly which physical files are marked for death
    files_to_remove = {}
    for cluster_id, data in manifest.items():
        if data.get("action").lower() == "remove":
            reason = data.get("reason", "duplicate_garbage")
            for filename in data.get("all_files", []):
                files_to_remove[filename] = reason

    if not files_to_remove:
        print("\nWARNING: You did not mark any clusters as 'remove' in the manifest.")
        print("Executing CDN relinking only. No deduplication will occur.\n")

    # 2. Group inventory by source JSON so we only open each massive file once
    json_tasks = {}
    for physical_filename, meta in inventory.items():
        src = meta["source_json"]
        if src not in json_tasks:
            json_tasks[src] = {}
        json_tasks[src][meta["internal_key"]] = physical_filename

    total_purged = 0
    total_kept = 0

    # 3. Process and Mutate each JSON file
    for json_path, keys_map in json_tasks.items():
        if not os.path.exists(json_path):
            print(f"Source file missing, skipping: {json_path}")
            continue

        print(f"Processing and cleaning: {os.path.basename(json_path)}")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        def mutate_node(node):
            nonlocal total_purged, total_kept
            if isinstance(node, dict):
                if "images" in node and isinstance(node["images"], dict):
                    # list() is required because we are mutating the dictionary during iteration
                    for img_key in list(node["images"].keys()):
                        b64_data = node["images"][img_key]
                        if not b64_data: continue

                        physical_file = keys_map.get(img_key)

                        if physical_file in files_to_remove:
                            # ACTION: Purge from JSON and replace with clean metadata tag
                            node["images"][img_key] = {
                                "status": "removed",
                                "reason": files_to_remove[physical_file]
                            }
                            total_purged += 1

                            # ACTION: Physically delete the garbage image from the master pool
                            img_path = os.path.join(MASTER_IMAGE_DIR, physical_file)
                            if os.path.exists(img_path):
                                os.remove(img_path)
                        else:
                            # ACTION: Keep the image, replace base64 with Cloudflare URL
                            if physical_file:
                                node["images"][img_key] = f"{CLOUDFLARE_BASE_URL}{physical_file}"
                                total_kept += 1

                for key, value in node.items():
                    if key != "images":
                        mutate_node(value)
                        
            elif isinstance(node, list):
                for item in node:
                    mutate_node(item)

        mutate_node(data)

        # 4. Save the Cleaned JSON safely without overwriting the original test file
        dir_name = os.path.dirname(json_path)
        base_name = os.path.basename(json_path).replace(".json", "_Cleaned.json")
        out_path = os.path.join(dir_name, base_name)

        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    print("\n--- STAGE 3 COMPLETE ---")
    print(f"Images Purged & Deleted: {total_purged}")
    print(f"Images Kept & CDN Linked: {total_kept}")
    print("Check your test folder for the newly generated '_Cleaned.json' files.")

if __name__ == "__main__":
    run_stage3_purge()