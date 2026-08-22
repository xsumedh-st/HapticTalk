"""
HapticTalk - back up samples/

Runs on your LAPTOP.

samples/ is in .gitignore, so it exists in exactly one place with no backup.
This zips it to a timestamped archive outside the repo.

Run:
    python backup_samples.py
"""

import datetime
import os
import zipfile

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(REPO_DIR, "samples")
BACKUP_DIR = os.path.join(os.path.expanduser("~"), "HapticTalk_backups")


def main():
    if not os.path.isdir(SAMPLES_DIR):
        print(f"No samples/ directory found at {SAMPLES_DIR}")
        return

    csv_files = sorted(f for f in os.listdir(SAMPLES_DIR) if f.endswith(".csv"))
    if not csv_files:
        print("samples/ has no CSV files, nothing to back up.")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(BACKUP_DIR, f"samples_{timestamp}.zip")

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in csv_files:
            zf.write(os.path.join(SAMPLES_DIR, fname), arcname=fname)

    size_kb = os.path.getsize(archive_path) / 1024
    print(f"Backed up {len(csv_files)} files ({size_kb:.1f} KB) to:")
    print(f"  {archive_path}")


if __name__ == "__main__":
    main()
