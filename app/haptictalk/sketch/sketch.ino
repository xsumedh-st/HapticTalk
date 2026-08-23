/*
 * HapticTalk - Haptic Engine with RouterBridge RPC
 *
 * Goes in:  sketch/sketch.ino
 *
 * Encoding:
 *   finger   -> semantic category
 *   S/L code -> word within that category
 *   envelope -> intent (neutral / urgent / question / affirmation)
 *
 * ALL meaning is carried by timing and rhythm, never amplitude. Coin ERMs
 * have too narrow a usable band for intensity to encode anything reliably.
 *
 * Non-blocking: patterns are built into a step queue and advanced from
 * millis(). Nothing here ever calls delay(), so the Bridge stays responsive.
 *
 * Exposed to Python via Bridge:
 *   play_haptic(word_index, modifier) -> int   queue a pattern
 *   haptic_busy()                     -> int   1 if currently playing
 *   stop_haptic()                     -> int   halt immediately
 *
 * Also accepts serial commands for bench testing (see handleSerialLine).
 */

#include "Arduino_RouterBridge.h"

// ---------------------------------------------------------------- pins

#define NUM_MOTORS 5

// 0=thumb 1=index 2=middle 3=ring 4=pinky
// Replace with the five PWM-capable pins you verified with motor_test.
const uint8_t MOTOR_PIN[NUM_MOTORS] = { 3, 5, 6, 9, 10 };

// ---------------------------------------------------------------- timing

const uint16_t SHORT_MS = 100;   // verified distinguishable from LONG
const uint16_t LONG_MS  = 300;
const uint16_t GAP_MS   = 120;
const uint16_t WORD_GAP = 200;

// Coin ERMs need ~2.3V to break static friction and 30-50ms to spin up.
// Each pulse opens at full PWM briefly so it is already spinning when it
// needs to register on the skin.
const uint16_t KICK_MS  = 25;
const uint8_t  KICK_INT = 255;

// One working level. Motor is 3.0V rated; ULN2003 drops ~1V from the 5V
// rail, so 200/255 puts roughly 3.1V across it.
const uint8_t INT_WORK = 200;

// ---------------------------------------------------------------- vocab

enum Symbol   : uint8_t { SYM_NONE = 0, SYM_S, SYM_L };
enum Modifier : uint8_t { MOD_NEUTRAL = 0, MOD_URGENT, MOD_QUESTION, MOD_AFFIRM };
enum Finger   : uint8_t { THUMB = 0, INDEX, MIDDLE, RING, PINKY };

struct WordEntry {
  const char* name;
  uint8_t finger;
  uint8_t s1;
  uint8_t s2;   // SYM_NONE for single-symbol words
};

// ORDER MATTERS. The Python side indexes into this same order.
const WordEntry VOCAB[] = {
  // THUMB - medical / urgent
  { "PAIN",          THUMB,  SYM_S, SYM_NONE },   //  0
  { "HELP",          THUMB,  SYM_L, SYM_NONE },   //  1
  { "DOCTOR",        THUMB,  SYM_S, SYM_S    },   //  2
  { "HOSPITAL",      THUMB,  SYM_S, SYM_L    },   //  3
  { "MEDICINE",      THUMB,  SYM_L, SYM_S    },   //  4

  // INDEX - needs
  { "WATER",         INDEX,  SYM_S, SYM_NONE },   //  5
  { "FOOD",          INDEX,  SYM_L, SYM_NONE },   //  6
  { "THIRSTY",       INDEX,  SYM_S, SYM_S    },   //  7

  // MIDDLE - identity
  { "I",             MIDDLE, SYM_S, SYM_NONE },   //  8
  { "NAME",          MIDDLE, SYM_L, SYM_NONE },   //  9
  { "DEAF",          MIDDLE, SYM_S, SYM_S    },   // 10
  { "BLIND",         MIDDLE, SYM_S, SYM_L    },   // 11
  { "AI",            MIDDLE, SYM_L, SYM_S    },   // 12

  // RING - social / meta
  { "TODAY",         RING,   SYM_S, SYM_NONE },   // 13
  { "GOODMORNING",   RING,   SYM_L, SYM_NONE },   // 14
  { "UNDERSTAND",    RING,   SYM_S, SYM_S    },   // 15
  { "COMMUNICATION", RING,   SYM_S, SYM_L    },   // 16
  { "DEMONSTRATE",   RING,   SYM_L, SYM_S    },   // 17

  // PINKY - responses
  { "YES",           PINKY,  SYM_S, SYM_NONE },   // 18
  { "NO",            PINKY,  SYM_L, SYM_NONE },   // 19
  { "PLEASE",        PINKY,  SYM_S, SYM_S    },   // 20
  { "THANKYOU",      PINKY,  SYM_S, SYM_L    },   // 21
  { "SORRY",         PINKY,  SYM_L, SYM_S    },   // 22
};

const uint8_t VOCAB_SIZE = sizeof(VOCAB) / sizeof(VOCAB[0]);

// ---------------------------------------------------------------- queue

struct Step {
  uint8_t  mask;
  uint8_t  intensity;
  uint16_t dur;
};

const uint8_t MAX_STEPS = 32;

Step          gQueue[MAX_STEPS];
uint8_t       gLen = 0, gIdx = 0;
unsigned long gStepStart = 0;
bool          gPlaying = false;

void pushStep(uint8_t mask, uint8_t intensity, uint16_t dur) {
  if (gLen >= MAX_STEPS) return;
  gQueue[gLen].mask      = mask;
  gQueue[gLen].intensity = intensity;
  gQueue[gLen].dur       = dur;
  gLen++;
}

void applyMask(uint8_t mask, uint8_t intensity) {
  for (uint8_t i = 0; i < NUM_MOTORS; i++) {
    analogWrite(MOTOR_PIN[i], (mask & (1 << i)) ? intensity : 0);
  }
}

void allOff() {
  for (uint8_t i = 0; i < NUM_MOTORS; i++) analogWrite(MOTOR_PIN[i], 0);
}

// ---------------------------------------------------------------- builder

uint16_t scaleDur(uint16_t d, bool urgent) {
  return urgent ? (uint16_t)((uint32_t)d * 6 / 10) : d;
}

void buildPattern(uint8_t wordIdx, uint8_t mod) {
  gLen = 0;
  gIdx = 0;
  if (wordIdx >= VOCAB_SIZE) return;

  const WordEntry& w = VOCAB[wordIdx];
  const uint8_t mask = (uint8_t)(1 << w.finger);
  const bool urgent  = (mod == MOD_URGENT);

  // Urgent alert burst: thumb + pinky only.
  // Each motor draws 120mA starting; five at once would brown out the board
  // on USB power. Thumb and pinky are also the most distinguishable pair.
  if (urgent) {
    for (uint8_t i = 0; i < 2; i++) {
      pushStep(0b10001, INT_WORK, 60);
      pushStep(0, 0, 60);
    }
    pushStep(0, 0, 100);
  }

  // The word itself
  uint8_t syms[2]  = { w.s1, w.s2 };
  uint8_t symCount = (w.s2 == SYM_NONE) ? 1 : 2;

  for (uint8_t i = 0; i < symCount; i++) {
    uint16_t dur = (syms[i] == SYM_S) ? SHORT_MS : LONG_MS;
    dur = scaleDur(dur, urgent);

    if (dur > KICK_MS + 20) {
      pushStep(mask, KICK_INT, KICK_MS);
      pushStep(mask, INT_WORK, dur - KICK_MS);
    } else {
      pushStep(mask, KICK_INT, dur);
    }

    if (i < symCount - 1) pushStep(0, 0, scaleDur(GAP_MS, urgent));
  }

  // Suffix flourishes - rhythmic, not amplitude-based
  if (mod == MOD_QUESTION) {
    pushStep(0, 0, WORD_GAP);
    for (uint8_t f = 0; f < NUM_MOTORS; f++) {
      pushStep((uint8_t)(1 << f), INT_WORK, 45);   // rising sweep
    }
  } else if (mod == MOD_AFFIRM) {
    pushStep(0, 0, WORD_GAP);
    pushStep(mask, INT_WORK, 60);
    pushStep(0, 0, 60);
    pushStep(mask, INT_WORK, 60);
  }

  pushStep(0, 0, 1);   // guarantee motors end off
}

// ---------------------------------------------------------------- player

void playWord(uint8_t wordIdx, uint8_t mod) {
  buildPattern(wordIdx, mod);
  if (gLen == 0) return;
  gIdx       = 0;
  gPlaying   = true;
  gStepStart = millis();
  applyMask(gQueue[0].mask, gQueue[0].intensity);
}

void stopHaptics() {
  gPlaying = false;
  gLen = 0;
  gIdx = 0;
  allOff();
}

void hapticUpdate() {
  if (!gPlaying) return;
  if (millis() - gStepStart >= gQueue[gIdx].dur) {
    gIdx++;
    if (gIdx >= gLen) { stopHaptics(); return; }
    gStepStart = millis();
    applyMask(gQueue[gIdx].mask, gQueue[gIdx].intensity);
  }
}

// ---------------------------------------------------------------- bridge API

// Called from Python: Bridge.call("play_haptic", index, modifier)
// Returns the index played, or -1 if rejected.
// Returns immediately - playback continues in loop().
int play_haptic(int wordIndex, int modifier) {
  if (wordIndex < 0 || wordIndex >= (int)VOCAB_SIZE) return -1;
  if (modifier < 0 || modifier > MOD_AFFIRM) modifier = MOD_NEUTRAL;

  playWord((uint8_t)wordIndex, (uint8_t)modifier);

  Monitor.print("play_haptic: ");
  Monitor.print(VOCAB[wordIndex].name);
  Monitor.print(" mod=");
  Monitor.println(modifier);

  return wordIndex;
}

// Python should check this before sending the next word, so patterns
// do not overlap into mush.
int haptic_busy() {
  return gPlaying ? 1 : 0;
}

int stop_haptic() {
  stopHaptics();
  return 0;
}

// ---------------------------------------------------------------- serial test

int8_t findWord(const char* name) {
  for (uint8_t i = 0; i < VOCAB_SIZE; i++) {
    if (strcasecmp(name, VOCAB[i].name) == 0) return (int8_t)i;
  }
  return -1;
}

uint8_t parseModifier(const char* s) {
  if (!s || !*s)                      return MOD_NEUTRAL;
  if (strcasecmp(s, "URGENT")   == 0) return MOD_URGENT;
  if (strcasecmp(s, "QUESTION") == 0) return MOD_QUESTION;
  if (strcasecmp(s, "AFFIRM")   == 0) return MOD_AFFIRM;
  return MOD_NEUTRAL;
}

void printVocab() {
  const char* fingerName[] = { "THUMB", "INDEX", "MIDDLE", "RING", "PINKY" };
  Serial.println(F("idx\tword\t\tfinger\tcode"));
  for (uint8_t i = 0; i < VOCAB_SIZE; i++) {
    Serial.print(i);          Serial.print(F("\t"));
    Serial.print(VOCAB[i].name); Serial.print(F("\t"));
    Serial.print(fingerName[VOCAB[i].finger]); Serial.print(F("\t"));
    Serial.print(VOCAB[i].s1 == SYM_S ? F("S") : F("L"));
    if (VOCAB[i].s2 != SYM_NONE) {
      Serial.print(F("-"));
      Serial.print(VOCAB[i].s2 == SYM_S ? F("S") : F("L"));
    }
    Serial.println();
  }
}

void handleSerialLine(char* line) {
  char* mod = strchr(line, ' ');
  if (mod) { *mod = '\0'; mod++; }

  if (strcasecmp(line, "LIST") == 0) { printVocab(); return; }
  if (strcasecmp(line, "STOP") == 0) { stopHaptics(); Serial.println(F("stopped")); return; }

  int8_t idx = findWord(line);
  if (idx < 0) { Serial.print(F("unknown: ")); Serial.println(line); return; }

  playWord((uint8_t)idx, parseModifier(mod));
  Serial.print(F("playing ")); Serial.println(VOCAB[idx].name);
}

// ---------------------------------------------------------------- sketch

char    lineBuf[48];
uint8_t lineLen = 0;

void setup() {
  for (uint8_t i = 0; i < NUM_MOTORS; i++) {
    pinMode(MOTOR_PIN[i], OUTPUT);
    analogWrite(MOTOR_PIN[i], 0);
  }

  Bridge.begin();
  Monitor.begin();

  Bridge.provide("play_haptic", play_haptic);
  Bridge.provide("haptic_busy", haptic_busy);
  Bridge.provide("stop_haptic", stop_haptic);

  Serial.begin(9600);
  Serial.println(F("=== HapticTalk engine ready ==="));
  printVocab();

  Monitor.println("Haptic bridge ready");
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (lineLen) { lineBuf[lineLen] = '\0'; handleSerialLine(lineBuf); lineLen = 0; }
    } else if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    }
  }

  hapticUpdate();   // must run every loop
}
