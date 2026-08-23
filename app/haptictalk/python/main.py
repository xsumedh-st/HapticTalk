"""
HapticTalk - full pipeline (python/main.py)

Runs on the UNO Q's Qualcomm Linux side.

  laptop (MediaPipe) --socket--> here
      -> buffer 30 frames
      -> Edge Impulse .eim inference   [ON DEVICE]
      -> sentence construction
      -> espeak out to JBL  +  haptics out to glove via Bridge

Setup on the board:
    chmod +x haptictalk.eim
    pip install edge-impulse-linux
    sudo apt install espeak-ng
"""

import os
import json
import socket
import subprocess
import threading
import time
from collections import deque

from arduino.app_utils import App, Bridge

# ================================================================ config

MODEL_PATH = os.path.join(os.path.dirname(__file__), "haptictalk.eim")

WINDOW_FRAMES   = 30      # frames per inference window
FEATURES_FRAME  = 126     # 2 hands x 21 landmarks x 3 coords
CONF_THRESHOLD  = 0.70   # below this, treat as "uncertain" and ignore
COOLDOWN_S      = 1.0    # min gap between accepting the same sign twice

# ---- false-positive guards (tune these) ----------------------------------
AGREE_WINDOWS   = 3   # label must win this many windows in a row
CLASSIFY_EVERY  = 1     # run inference every Nth frame
MIN_HAND_FRAC   = 0.80   # this much of the window must contain a hand
MAX_MOTION      = 999  # reject windows where the hand is still moving
DEBUG_REJECTS   = False   # print why windows were rejected (turn OFF for demo)



LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 5005

# ================================================================ haptics

HAPTIC_WORDS = [
    "PAIN", "HELP", "DOCTOR", "HOSPITAL", "MEDICINE",
    "WATER", "FOOD", "THIRSTY",
    "I", "NAME", "DEAF", "BLIND", "AI",
    "TODAY", "GOODMORNING", "UNDERSTAND", "COMMUNICATION", "DEMONSTRATE",
    "YES", "NO", "PLEASE", "THANKYOU", "SORRY",
]
HAPTIC_INDEX = {w: i for i, w in enumerate(HAPTIC_WORDS)}

NEUTRAL, URGENT, QUESTION, AFFIRM = 0, 1, 2, 3
URGENT_WORDS = {"PAIN", "HELP", "DOCTOR", "HOSPITAL", "MEDICINE"}


def play_haptic(word, modifier=None, wait=False):
    word = word.upper()
    if word not in HAPTIC_INDEX:
        return False
    if modifier is None:
        modifier = URGENT if word in URGENT_WORDS else NEUTRAL
    try:
        r = Bridge.call("play_haptic", HAPTIC_INDEX[word], modifier)
    except Exception as e:
        print(f"[haptic] bridge error: {e}")
        return False
    if r is None or r < 0:
        return False
    if wait:
        deadline = time.time() + 5
        while time.time() < deadline and Bridge.call("haptic_busy"):
            time.sleep(0.02)
    return True


# ================================================================ speech

# The container has no sudo and cannot reach lightdm's PipeWire session, so
# speech goes to a relay script running on the host. Start it with:
#     nohup python3 ~/tts_relay.py > /tmp/tts_relay.log 2>&1 &
TTS_HOST = "172.17.0.1"      # docker bridge gateway = the host
TTS_PORT = 5006


def say(text):
    """Send text to the host TTS relay."""
    print(f"[speech] {text}")
    try:
        s = socket.create_connection((TTS_HOST, TTS_PORT), timeout=3)
        s.sendall((text + "\n").encode("utf-8"))
        s.close()
    except Exception as e:
        print(f"[speech] relay unreachable: {e}")


def keepalive_loop():
    """JBL Go 3 sleeps when idle and clips the next sentence.
    A near-silent blip every 60s keeps the A2DP link awake."""
    while True:
        time.sleep(60)
        try:
            s = socket.create_connection((TTS_HOST, TTS_PORT), timeout=3)
            s.sendall(b".\n")
            s.close()
        except Exception:
            pass


# ================================================================ grammar

INTRO_PATTERNS = {
    ("GOODMORNING", "I", "NAME"):  "Good morning, my name is Sumedh.",
    ("TODAY", "I", "DEMONSTRATE"): "Today I will be demonstrating",
    ("AI", "COMMUNICATION"):       "HapticTalk, an AI-powered communication glove",
    ("HELP", "DEAF"):              "that helps the deaf speak,",
    ("HELP", "BLIND"):             "and lets a deaf-blind person feel the reply on their fingertips.",
}

GENERAL_PATTERNS = {
    ("I", "PAIN", "DOCTOR"):  "I am in pain, please call a doctor.",
    ("PLEASE", "DOCTOR"):     "Please call a doctor immediately.",
    ("DOCTOR", "HOSPITAL"):   "Please take me to the hospital.",
    ("I", "MEDICINE"):        "I need my medicine urgently.",
    ("I", "PAIN"):            "I am in pain.",
    ("I", "HELP"):            "I need help.",
    ("I", "THIRSTY"):         "I am thirsty, I need water.",
    ("I", "WATER"):           "I need water.",
    ("I", "FOOD"):            "I am hungry, I need food.",
    ("PLEASE", "UNDERSTAND"): "Please help me, I don't understand.",
    ("SORRY", "UNDERSTAND"):  "I am sorry, I don't understand.",
    ("I", "UNDERSTAND"):      "I understand, thank you.",
    ("THANKYOU", "HELP"):     "Thank you for your help.",
    ("GOODMORNING", "HELP"):  "Good morning, can you please help me?",
    ("I", "NAME"):            "My name is Sumedh.",
    ("I", "DEAF"):            "I am deaf.",
}

SINGLE_WORD_OK = {
     "AI":            "A.I.",
    "BLIND":         "Blind.",
    "COMMUNICATION": "Communication.",
    "DEMONSTRATE":   "Demonstrate.",
    "DOCTOR":        "Doctor.",
    "FOOD":          "Food.",
    "HOSPITAL":      "Hospital.",
    "I":             "I.",
    "MEDICINE":      "Medicine.",
    "NAME":          "Name.",
    "THIRSTY":       "Thirsty.",
    "TODAY":         "Today.",
    "UNDERSTAND":    "Understand.",
        "DEAF":        "I am deaf.",
    "HELP":        "Help!",
    "GOODMORNING": "Good morning.",
        "THANKYOU":    "Thank you.",
}

ALL_PATTERNS = sorted(
    list(INTRO_PATTERNS.items()) + list(GENERAL_PATTERNS.items()),
    key=lambda kv: len(kv[0]), reverse=True,
)

BUFFER_TIMEOUT = 6.0
MAX_BUFFER = 5

sign_buffer = []
last_sign_time = 0.0


def match_pattern(buf):
    t = tuple(buf)
    for pattern, sentence in ALL_PATTERNS:
        if len(pattern) <= len(t) and t[-len(pattern):] == pattern:
            return sentence
    return None


def could_grow(buf):
    t = tuple(buf)
    for pattern, _ in ALL_PATTERNS:
        if len(pattern) > len(t) and pattern[:len(t)] == t:
            return True
    return False


def emit(sentence):
    say(sentence)
    return sentence



def process_sign(label):
    """Feed one recognised sign. Speaks when a phrase completes."""
    global sign_buffer, last_sign_time

    now = time.time()
    if now - last_sign_time > BUFFER_TIMEOUT:
        sign_buffer = []
    last_sign_time = now

    sign_buffer.append(label.upper())
    print(f"[buffer] {sign_buffer}")
    if len(sign_buffer) > MAX_BUFFER:
        sign_buffer.pop(0)

    play_haptic(label)          # glove echoes every recognised sign

    sentence = match_pattern(sign_buffer)
    if sentence and not could_grow(sign_buffer):
        sign_buffer = []
        return emit(sentence)

    if could_grow(sign_buffer):
        return None             # wait, a longer phrase may be coming

    last = sign_buffer[-1]
    sign_buffer = []
    return emit(SINGLE_WORD_OK.get(last, last.capitalize() + "."))


def flush_loop():
    """Commits a buffered phrase once the signer pauses."""
    global sign_buffer
    while True:
        time.sleep(0.3)
        if not sign_buffer:
            continue
        if time.time() - last_sign_time < BUFFER_TIMEOUT:
            continue
        sentence = match_pattern(sign_buffer)
        last = sign_buffer[-1]
        sign_buffer = []
        emit(sentence or SINGLE_WORD_OK.get(last, last.capitalize() + "."))


# ================================================================ inference

runner = None
frame_buffer = deque(maxlen=WINDOW_FRAMES)
last_label = None
last_label_time = 0.0
recent_labels = deque(maxlen=AGREE_WINDOWS)
frames_since_classify = 0


def init_model():
    global runner
    from edge_impulse_linux.runner import ImpulseRunner

    print(f"[model] loading {MODEL_PATH}")
    runner = ImpulseRunner(MODEL_PATH)
    info = runner.init()

    params = info.get("model_parameters", {})
    expected = params.get("input_features_count", "unknown")
    print(f"[model] {info.get('project', {}).get('name', '?')}")
    print(f"[model] expects {expected} features "
          f"(we send {WINDOW_FRAMES * FEATURES_FRAME})")
    print(f"[model] labels: {params.get('labels', [])}")
    return info


def _hand_fraction():
    """Fraction of frames in the window that actually contain a hand."""
    if not frame_buffer:
        return 0.0
    n = sum(1 for f in frame_buffer if any(abs(v) > 1e-6 for v in f))
    return n / len(frame_buffer)


def _motion():
    """Mean per-feature change between consecutive frames. High = still moving."""
    fb = list(frame_buffer)
    if len(fb) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(fb, fb[1:]):
        total += sum(abs(x - y) for x, y in zip(a, b)) / len(a)
    return total / (len(fb) - 1)


def classify_window():
    """Run inference on the current 30-frame buffer."""
    global last_label, last_label_time, frames_since_classify

    if len(frame_buffer) < WINDOW_FRAMES:
        return None

    frames_since_classify += 1
    if frames_since_classify < CLASSIFY_EVERY:
        return None
    frames_since_classify = 0

    hand_frac = _hand_fraction()
    if hand_frac < MIN_HAND_FRAC:
        recent_labels.clear()
        return None

    motion = _motion()
    if motion > MAX_MOTION:
        recent_labels.clear()
        if DEBUG_REJECTS:
            print(f"[skip] still moving (motion {motion:.4f})")
        return None

    features = []
    for frame in frame_buffer:
        features.extend(frame)

    t0 = time.time()
    try:
        res = runner.classify(features)
    except Exception as e:
        print(f"[model] classify failed: {e}")
        return None
    elapsed_ms = (time.time() - t0) * 1000

    scores = res["result"]["classification"]
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    label, conf = ranked[0]
    second = ranked[1] if len(ranked) > 1 else ("-", 0.0)

    if conf < CONF_THRESHOLD:
        recent_labels.clear()
        if DEBUG_REJECTS:
            print(f"[skip] {label} {conf:.2f} below {CONF_THRESHOLD}")
        return None

    recent_labels.append(label)
    if len(recent_labels) < AGREE_WINDOWS or len(set(recent_labels)) > 1:
        if DEBUG_REJECTS:
            print(f"[hold] {label} {conf:.2f} "
                  f"({len(recent_labels)}/{AGREE_WINDOWS}, motion {motion:.4f})")
        return None

    now = time.time()
    if label == last_label and (now - last_label_time) < COOLDOWN_S:
        recent_labels.clear()
        return None

    last_label = label
    last_label_time = now
    recent_labels.clear()

    print(f"[infer] {label} {conf:.2f}  ({elapsed_ms:.1f} ms, motion {motion:.4f})")
    return label

# ================================================================ socket
def haptic_server():
    """Accept 'WORD' lines and buzz the glove. Speech -> touch."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((LISTEN_HOST, HAPTIC_PORT))
    srv.listen(5)
    print(f"[haptic] listening on {LISTEN_HOST}:{HAPTIC_PORT}")

    while True:
        try:
            conn, addr = srv.accept()
            data = conn.recv(1024).decode("utf-8", errors="ignore")
            conn.close()
            for line in data.splitlines():
                word = line.strip().upper()
                if not word:
                    continue
                if word in HAPTIC_INDEX:
                    print(f"[haptic] {word}")
                    play_haptic(word)
                else:
                    print(f"[haptic] unknown word: {word!r}")
        except Exception as e:
            print(f"[haptic] error: {e}")
            
def landmark_server():
    """Receive landmark frames from the laptop.

    Expects one CSV line per frame: 126 comma-separated floats
    (left hand 63, then right hand 63), newline terminated.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((LISTEN_HOST, LISTEN_PORT))
    srv.listen(1)
    print(f"[net] listening on {LISTEN_HOST}:{LISTEN_PORT}")

    while True:
        conn, addr = srv.accept()
        print(f"[net] connected: {addr}")
        buf = ""
        frames_in = 0
        try:
            while True:
                data = conn.recv(8192)
                if not data:
                    break
                buf += data.decode("utf-8", errors="ignore")

                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("HAPTIC "):
                        word = line[7:].strip().upper()
                        if word in HAPTIC_INDEX:
                            print(f"[haptic] {word}")
                            play_haptic(word)
                        else:
                            print(f"[haptic] unknown: {word!r}")
                        continue
                    try:
                        lm = [float(v) for v in line.split(",")]
                    except ValueError:
                        continue

                    if len(lm) != FEATURES_FRAME:
                        bad_frames +=1
                        if frames_in == 1:
                             print(f"[net] BAD FRAME #{bad_frames}: got {len(lm)}, expected {FEATURES_FRAME}")
                        continue

                    frames_in += 1
                    if frames_in == 1:
                        print("[net] receiving landmarks")

                    frame_buffer.append(lm)
                    label = classify_window()
                    if label:
                        process_sign(label)
        except Exception as e:
            print(f"[net] connection error: {e}")
        finally:
            conn.close()
            frame_buffer.clear()
            print(f"[net] disconnected ({frames_in} frames received)")


# ================================================================ main

def start():
    time.sleep(2)                     # let the MCU come up
    init_model()

    say("HapticTalk ready")

    threading.Thread(target=flush_loop, daemon=True).start()
    threading.Thread(target=keepalive_loop, daemon=True).start()
    threading.Thread(target=haptic_server, daemon=True).start()
    threading.Thread(target=landmark_server, daemon=True).start()
    

if __name__ == "__main__":
    start()
    App.run()