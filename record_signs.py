import cv2
import csv
import os
import time

from hands_config import make_hands

hands = make_hands()
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
time.sleep(2)

os.makedirs("samples", exist_ok=True)


SIGNS = [
     "MEDICINE","THIRSTY","DEMONSTRATE"
]

WINDOW_FRAMES = 30
SAMPLES_NEEDED = 30
TARGET_FPS = 15
FRAME_INTERVAL = 1.0 / TARGET_FPS
COUNTDOWN_DURATION = 1.5
REST_BETWEEN_SAMPLES = 0.5  # short pause between auto-samples

def extract_landmarks(hand_landmarks):
    values = []
    for lm in hand_landmarks.landmark:
        values.extend([round(lm.x, 4), round(lm.y, 4), round(lm.z, 4)])
    return values

current_sign_idx = 0
sample_count = 0
state = "IDLE"  # IDLE → COUNTDOWN → RECORDING → REST → COUNTDOWN (auto loop)

frame_buffer = []
last_frame_time = 0
countdown_start = 0
rest_start = 0
session_active = False

print("\n=== HAPTICTALK AUTO RECORDER ===")
print("SPACE = begin session for current sign (records all 30 samples automatically)")
print("N     = skip to next sign")
print("Q     = quit\n")

while current_sign_idx < len(SIGNS):
    current_label = SIGNS[current_sign_idx]
    success, frame = cap.read()
    if not success:
        continue

    now = time.time()
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    left_data = [0.0] * 63
    right_data = [0.0] * 63

    if results.multi_hand_landmarks:
        for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
            label = results.multi_handedness[idx].classification[0].label
            vals = extract_landmarks(hand_landmarks)
            if label == "Left":
                left_data = vals
            else:
                right_data = vals

    current_frame_data = left_data + right_data
    hand_detected = results.multi_hand_landmarks is not None

    # --- STATE MACHINE ---

    if state == "IDLE":
        pass  # waiting for SPACE

    elif state == "COUNTDOWN":
        elapsed = now - countdown_start
        if elapsed >= COUNTDOWN_DURATION:
            state = "RECORDING"
            frame_buffer = []
            last_frame_time = 0

    elif state == "RECORDING":
        if now - last_frame_time >= FRAME_INTERVAL:
            frame_buffer.append(current_frame_data)
            last_frame_time = now

        if len(frame_buffer) >= WINDOW_FRAMES:
            # Save sample
            filepath = f"samples/{current_label}.csv"
            write_header = not os.path.exists(filepath)
            with open(filepath, "a", newline="") as f:
                writer = csv.writer(f)
                if write_header:
                    header = []
                    for fr in range(WINDOW_FRAMES):
                        for feat in range(126):
                            header.append(f"fr{fr}_f{feat}")
                    header.append("label")
                    writer.writerow(header)
                flat = [v for frame_data in frame_buffer for v in frame_data]
                writer.writerow(flat + [current_label])

            sample_count += 1
            print(f"  ✅ {current_label} — sample {sample_count}/{SAMPLES_NEEDED}")
            frame_buffer = []

            if sample_count >= SAMPLES_NEEDED:
                print(f"\n✅ {current_label} complete!\n")
                state = "IDLE"
                session_active = False
                current_sign_idx += 1
                sample_count = 0
            else:
                # Auto-rest then auto-record next sample
                state = "REST"
                rest_start = now

    elif state == "REST":
        if now - rest_start >= REST_BETWEEN_SAMPLES:
            state = "COUNTDOWN"
            countdown_start = now

    # --- UI ---
    cv2.rectangle(frame, (0, 0), (640, 175), (0, 0, 0), -1)

    if current_sign_idx < len(SIGNS):
        cv2.putText(frame, f"SIGN: {current_label}", (10, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)

    dot_color = (0, 255, 0) if hand_detected else (0, 0, 255)
    cv2.circle(frame, (615, 22), 10, dot_color, -1)
    cv2.putText(frame, "HAND" if hand_detected else "NO HAND",
                (555, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.4, dot_color, 1)

    if state == "IDLE":
        if not session_active:
            cv2.putText(frame, "Press SPACE to begin recording all 30 samples",
                        (10, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 100), 1)
            cv2.putText(frame, "Keep signing continuously once started",
                        (10, 108), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150, 150, 150), 1)

    elif state == "COUNTDOWN":
        remaining = max(0, COUNTDOWN_DURATION - (now - countdown_start))
        cv2.putText(frame, f"GET READY {remaining:.1f}s",
                    (10, 82), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 165, 255), 2)

    elif state == "RECORDING":
        progress = len(frame_buffer) / WINDOW_FRAMES
        cv2.putText(frame, f"RECORDING sample {sample_count + 1}/{SAMPLES_NEEDED}",
                    (10, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        bar_fill = int(580 * progress)
        cv2.rectangle(frame, (10, 130), (590, 150), (60, 60, 60), -1)
        cv2.rectangle(frame, (10, 130), (10 + bar_fill, 150), (0, 0, 255), -1)
        cv2.rectangle(frame, (10, 130), (590, 150), (255, 255, 255), 1)

    elif state == "REST":
        cv2.putText(frame, f"Keep signing... next sample in {REST_BETWEEN_SAMPLES:.1f}s",
                    (10, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 255, 100), 1)

    signs_left = len(SIGNS) - current_sign_idx
    cv2.putText(frame, f"{signs_left} signs remaining  |  N=skip  Q=quit",
                (10, 162), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1)

    cv2.imshow("HapticTalk Auto Recorder", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break
    elif key == ord(' ') and state == "IDLE":
        filepath = f"samples/{current_label}.csv"
        if os.path.exists(filepath):
            with open(filepath) as f:
                existing_count = sum(1 for _ in f) - 1  # minus header row
            confirm = input(
                f"⚠ This will DELETE {existing_count} existing samples for "
                f"{current_label} and re-record from scratch. Type y to confirm: "
            )
            if confirm.strip().lower() != 'y':
                print("Cancelled — existing samples kept.")
                continue
            os.remove(filepath)
        session_active = True
        state = "COUNTDOWN"
        countdown_start = now
        sample_count = 0
        print(f"▶ Starting {current_label} — keep signing continuously...")
    elif key == ord('n'):
        state = "IDLE"
        session_active = False
        print(f"⏭ Skipped {current_label}")
        current_sign_idx += 1
        sample_count = 0

cap.release()
cv2.destroyAllWindows()
print("\nSession complete. Files saved in /samples/")
for f in sorted(os.listdir("samples")):
    if f.endswith(".csv"):
        with open(f"samples/{f}") as file:
            count = sum(1 for _ in file) - 1
        print(f"  {f}: {count} samples")