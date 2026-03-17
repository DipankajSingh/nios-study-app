import os
import json
import base64
from pathlib import Path

# --- CONFIG ---
# Point this to your isolated test folder containing the 3 JSONs
TEST_DATA_DIR = "./json" 
MASTER_IMAGE_DIR = "./master_image_pool"
INVENTORY_FILE = "./image_inventory.json"

def run_mass_extraction():
    input_path = Path(TEST_DATA_DIR)
    os.makedirs(MASTER_IMAGE_DIR, exist_ok=True)
    
    # Grab all JSONs in your test sandbox
    valid_json_files = [
        f for f in input_path.rglob("*.json")
        if "_manifest" not in f.name and "Cleaned" not in f.name
    ]
    
    if not valid_json_files:
        print(f"Error: No valid JSONs found in {TEST_DATA_DIR}")
        return

    print(f"SANDBOX MODE ACTIVE: Found {len(valid_json_files)} test files.\n")
    
    inventory = {}
    total_images = 0

    for json_file in valid_json_files:
        rel_path = json_file.relative_to(input_path)
        
        # Safe extraction of the subject name (prevents crashes on flat folders)
        if len(rel_path.parts) >= 3:
            subject_folder = rel_path.parts[-3]
        elif len(rel_path.parts) >= 2:
            subject_folder = rel_path.parts[-2]
        else:
            subject_folder = "test-subject"
            
        chapter_name = json_file.stem.replace(" ", "")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"CORRUPT JSON: {json_file}")
                continue

        def extract_all(node):
            nonlocal total_images
            if isinstance(node, dict):
                if "images" in node and isinstance(node["images"], dict):
                    for img_key, b64_data in node["images"].items():
                        if not b64_data: continue
                        
                        try:
                            # Strip the base64 prefix if Marker attached it
                            if b64_data.startswith("data:image"):
                                b64_data = b64_data.split(",")[1]
                                
                            img_bytes = base64.b64decode(b64_data)
                            
                            # Build the physical filename
                            safe_key = img_key.replace("/", "_").strip("_")
                            unique_filename = f"{subject_folder}_{chapter_name}_{safe_key}.jpeg"
                            output_path = os.path.join(MASTER_IMAGE_DIR, unique_filename)
                            
                            # Save physical file
                            with open(output_path, "wb") as img_file:
                                img_file.write(img_bytes)
                                
                            # Log it in the inventory
                            inventory[unique_filename] = {
                                "source_json": str(json_file),
                                "internal_key": img_key
                            }
                            
                            total_images += 1
                            
                        except Exception as e:
                            print(f"Failed extracting {img_key} from {json_file.name}: {e}")

                for key, value in node.items():
                    if key != "images":
                        extract_all(value)
                        
            elif isinstance(node, list):
                for item in node:
                    extract_all(item)

        extract_all(data)
        print(f"Successfully Processed: {json_file.name}")

    with open(INVENTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(inventory, f, indent=4)
        
    print(f"\nSANDBOX EXTRACTION COMPLETE.")
    print(f"Total Images Extracted: {total_images}")
    print(f"Inventory saved to: {INVENTORY_FILE}")

if __name__ == "__main__":
    run_mass_extraction()