import json, os, pwd, subprocess, sys, time

CLIPS = "/home/arduino/audio_clips"
GAP   = float(sys.argv[1]) if len(sys.argv) > 1 else 0.25

LINES = [
    "Good morning, my name is Sumedh.",
    "Today I will be demonstrating",
    "HapticTalk, an AI-powered communication glove",
    "that helps the deaf speak,",
    "and lets a deaf-blind person feel the reply on their fingertips.",
]

uid = pwd.getpwnam("lightdm").pw_uid
with open(os.path.join(CLIPS, "manifest.json"), encoding="utf-8") as f:
    manifest = json.load(f)

missing = [l for l in LINES if l not in manifest]
if missing:
    print("No clip for these lines:")
    for m in missing:
        print("   ", repr(m))
    sys.exit(1)

for line in LINES:
    path = os.path.join(CLIPS, manifest[line])
    print(f"-> {line}")
    subprocess.run(
        ["sudo", "-n", "-u", "lightdm",
         "env", f"XDG_RUNTIME_DIR=/run/user/{uid}",
         "mpg123", "-q", path],
        check=False,
    )
    time.sleep(GAP)

print("done")
