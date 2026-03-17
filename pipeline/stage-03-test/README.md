# Stage 03 — Image Deduplication Pipeline (Test Sandbox)

This folder contains a 3-step pipeline for extracting, deduplicating, and CDN-relinking images embedded in the structured chapter JSON files produced by earlier pipeline stages.

Run the scripts **in order**. Each step produces outputs that the next step depends on.

---

## Prerequisites

```bash
pip install fastdup pandas
```

Place your test chapter JSON files (output from Stage 02) inside the `./json/` directory before starting.

---

## Step 1 — Mass Image Extraction (`test_step_1.py`)

Walks all JSON files in `./json/`, finds every base64-encoded image stored under `"images"` keys, decodes them, and saves each as a physical `.jpeg` file in a flat master pool directory.

**Run:**

```bash
python test_step_1.py
```

**Inputs:**

- `./json/` — chapter JSON files from the extraction stage

**Outputs:**

- `./master_image_pool/` — all decoded images, named `{subject}_{chapter}_{key}.jpeg`
- `./image_inventory.json` — maps every physical filename back to its source JSON and internal image key

**Key config variables (top of file):**

| Variable           | Default                  | Description                      |
| ------------------ | ------------------------ | -------------------------------- |
| `TEST_DATA_DIR`    | `./json`                 | Folder containing chapter JSONs  |
| `MASTER_IMAGE_DIR` | `./master_image_pool`    | Output folder for decoded images |
| `INVENTORY_FILE`   | `./image_inventory.json` | Inventory manifest path          |

---

## Step 2 — Perceptual Clustering & Gallery (`test_step_2.py`)

Runs [fastdup](https://github.com/visual-layer/fastdup) perceptual hashing on all images in the master pool to find near-duplicate groups (e.g. repeated logos, dividers, watermarks). Generates a JSON manifest and an HTML gallery for human review.

**Run:**

```bash
python test_step_2.py
```

**Inputs:**

- `./master_image_pool/` — images extracted in Step 1

**Outputs:**

- `./fastdup_workdir/` — fastdup working files and similarity index
- `./cluster_review_manifest.json` — one entry per duplicate cluster; you edit the `"action"` field here
- `./manual_review.html` — visual gallery; open in a browser to inspect clusters

**After running**, open `manual_review.html` in your browser. For each cluster that contains garbage images (logos, lines, repeated decorations), open `cluster_review_manifest.json` and change:

```json
"action": "keep"
```

to:

```json
"action": "remove",
"reason": "repeated_logo"
```

Leave genuine content clusters set to `"keep"`.

**Key config variables:**

| Variable               | Default                          | Description               |
| ---------------------- | -------------------------------- | ------------------------- |
| `MASTER_IMAGE_DIR`     | `./master_image_pool`            | Image pool from Step 1    |
| `FASTDUP_WORK_DIR`     | `./fastdup_workdir`              | fastdup scratch directory |
| `REVIEW_MANIFEST_FILE` | `./cluster_review_manifest.json` | Editable cluster manifest |
| `OUTPUT_HTML`          | `./manual_review.html`           | Visual review gallery     |

---

## Step 3 — Purge & CDN Relink (`test_step_3.py`)

Reads your reviewed manifest and applies the decisions:

- **`"action": "remove"`** — deletes the physical image from `master_image_pool` and replaces its base64 payload in the source JSON with a `{"status": "removed", "reason": "..."}` tombstone.
- **`"action": "keep"`** — replaces the base64 payload with a Cloudflare CDN URL pointing to the physical file.

Source JSONs are **not overwritten**. A new `_Cleaned.json` file is written alongside each original.

**Run:**

```bash
python test_step_3.py
```

**Inputs:**

- `./image_inventory.json` — from Step 1
- `./cluster_review_manifest.json` — edited after Step 2
- `./master_image_pool/` — physical images
- Original chapter JSONs referenced in the inventory

**Outputs:**

- `*_Cleaned.json` files — original chapter JSONs with base64 replaced by CDN URLs or tombstones
- Physical garbage images deleted from `./master_image_pool/`

**Key config variables:**

| Variable               | Default                            | Description                    |
| ---------------------- | ---------------------------------- | ------------------------------ |
| `INVENTORY_FILE`       | `./image_inventory.json`           | Inventory from Step 1          |
| `REVIEW_MANIFEST_FILE` | `./cluster_review_manifest.json`   | Reviewed manifest from Step 2  |
| `MASTER_IMAGE_DIR`     | `./master_image_pool`              | Physical image pool            |
| `CLOUDFLARE_BASE_URL`  | `https://your-app.cloudflare.com/` | **Change this** before running |

> **Important:** Set `CLOUDFLARE_BASE_URL` to your actual R2 / CDN bucket URL before running Step 3, or the generated links will be placeholders.

---

## Full Pipeline Summary

```
./json/*.json
      │
      ▼
[Step 1] test_step_1.py
      │   Decode & extract base64 images
      ▼
./master_image_pool/   +   image_inventory.json
      │
      ▼
[Step 2] test_step_2.py
      │   Perceptual deduplication (fastdup)
      ▼
cluster_review_manifest.json   +   manual_review.html
      │
      │  (human edits manifest)
      │
      ▼
[Step 3] test_step_3.py
      │   Purge garbage, relink survivors to CDN
      ▼
./json/*_Cleaned.json   (base64 replaced with CDN URLs)
```

---

## File Reference

| File                           | Purpose                                         |
| ------------------------------ | ----------------------------------------------- |
| `test_step_1.py`               | Extract & decode images from chapter JSONs      |
| `test_step_2.py`               | Cluster similar images, generate review gallery |
| `test_step_3.py`               | Purge marked images, relink kept images to CDN  |
| `image_inventory.json`         | Generated — image-to-source mapping             |
| `cluster_review_manifest.json` | Generated then **human-edited**                 |
| `manual_review.html`           | Generated — open in browser for visual review   |
| `fastdup_workdir/`             | Generated — fastdup internal index files        |
| `master_image_pool/`           | Generated — flat pool of all extracted images   |
