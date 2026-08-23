import asyncio, hashlib, json, os
import edge_tts

OUTDIR = "/home/arduino/audio_clips"
VOICE  = "en-IN-NeerjaNeural"   # must match generate_audio.py exactly
RATE   = "-5%"                  # must match generate_audio.py exactly

NEW = [
    "A.I.", "Blind.", "Communication.", "Demonstrate.", "Doctor.",
    "Food.", "Hospital.", "I.", "Medicine.", "Name.",
    "Thirsty.", "Today.", "Understand.",
]

def key_for(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]

async def main():
    mpath = os.path.join(OUTDIR, "manifest.json")
    with open(mpath, encoding="utf-8") as f:
        manifest = json.load(f)

    for text in NEW:
        if text in manifest:
            print(f"skip  {text!r} already has a clip")
            continue
        fname = f"{key_for(text)}.mp3"
        path = os.path.join(OUTDIR, fname)
        try:
            await edge_tts.Communicate(text, VOICE, rate=RATE).save(path)
        except Exception as e:
            print(f"FAIL  {text!r}: {type(e).__name__}: {e}")
            continue
        size = os.path.getsize(path)
        if size == 0:
            print(f"FAIL  {text!r}: 0 bytes")
            continue
        manifest[text] = fname
        print(f"ok    {text!r} -> {fname} ({size} bytes)")

    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nmanifest now has {len(manifest)} entries")

asyncio.run(main())
