"""
HapticTalk - upload recorded samples to Edge Impulse

Runs on your LAPTOP.

Requires the EI_API_KEY environment variable (Edge Impulse → project → Keys).
Set it before running, in PowerShell:

    $env:EI_API_KEY = "ei_..."
    python upload_to_ei.py

This only sets it for the current PowerShell session. To persist it across
sessions, use:

    setx EI_API_KEY "ei_..."
"""

import requests
import os
import csv

EI_API_KEY = os.environ["EI_API_KEY"]
PROJECT_ID = "1059595"    # get from Edge Impulse → project → Keys
SAMPLES_DIR = "samples"

# FUNCTION DEFINITION FIRST
def upload_csv(filepath, label):
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)

    for i, row in enumerate(rows):
        files = {
            'data': (f'{label}_{i}.csv',
                    '\n'.join([','.join(headers[:-1]), ','.join(row[:-1])]),
                    'text/csv')
        }
        response = requests.post(
            'https://ingestion.edgeimpulse.com/api/training/files',
            headers={
                'x-api-key': EI_API_KEY,
                'x-label': label,
            },
            files=files
        )
        if response.status_code == 200:
            print(f"✅ {label} sample {i+1}/{len(rows)}")
        else:
            print(f"❌ {label} sample {i+1} failed: {response.text[:100]}")

# THEN THE LOOP
SIGNS_TO_UPLOAD = ["UNDERSTAND", "WATER", "YES"]

for filename in sorted(os.listdir(SAMPLES_DIR)):
    if filename.endswith('.csv'):
        label = filename.replace('.csv', '')
        if label not in SIGNS_TO_UPLOAD:
            continue
        filepath = os.path.join(SAMPLES_DIR, filename)
        print(f"\nUploading {label}...")
        upload_csv(filepath, label)

print("\n✅ All uploads complete")