"""
Invoked by the main app as a subprocess:
    python export_worker.py <job_json_path>

The job JSON has the shape:
{
    "original_folder": "...",
    "new_folder":      "...",
    "mouse_number":    "...",
    "eye":             "...",
    "first_image_size": [w, h],
    "sequence":        [[modality, label], ...],
    "assignments":     {"0": "/path/img.tif", "1": null, ...},
    "extension":       ".tif"
}

On completion (or error) it writes a sentinel file next to the job JSON:
    <job_json_path>.done   – contains {"status": "ok",    "new_folder": "..."}
    <job_json_path>.done   – contains {"status": "error", "message":    "..."}
"""

import json
import os
import shutil
import sys

from PIL import Image


def run(job_path: str):
    with open(job_path, "r") as f:
        job = json.load(f)

    new_folder       = job["new_folder"]
    mouse_number     = job["mouse_number"]
    eye              = job["eye"]
    first_image_size = tuple(job["first_image_size"])
    sequence         = job["sequence"]           # [[modality, label], ...]
    assignments      = job["assignments"]        # {"0": path_or_null, ...}
    ext              = job["extension"]

    os.makedirs(new_folder, exist_ok=True)

    for idx, (modality, _) in enumerate(sequence):
        new_filename  = f"{idx:03d}_{mouse_number}_{eye}_{modality}{ext}"
        new_path      = os.path.join(new_folder, new_filename)
        assigned_path = assignments.get(str(idx))

        if assigned_path:
            # copyfile is faster than copy2 – skips metadata
            shutil.copyfile(assigned_path, new_path)
        else:
            img = Image.new("RGB", first_image_size, (0, 0, 0))
            img.save(new_path)


def main():
    if len(sys.argv) != 2:
        print("Usage: export_worker.py <job_json_path>", file=sys.stderr)
        sys.exit(1)

    job_path  = sys.argv[1]
    done_path = job_path + ".done"

    try:
        run(job_path)
        result = {"status": "ok", "new_folder": json.load(open(job_path))["new_folder"]}
    except Exception as exc:
        result = {"status": "error", "message": str(exc)}

    with open(done_path, "w") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()