// /*
//  * HapticTalk - motor calibration
//  *
//  * Run this AFTER taping the motors to the glove. Tape position and pressure
//  * change how a motor feels, so thresholds measured on the bench are wrong once
//  * it is mounted.
//  *
//  * Serial Monitor @ 115200, line ending: Newline
//  *
//  *   HELP              command list
//  *   ID                play each finger in order, announcing it - checks wiring
//  // *   T <n> <pwm> <ms>  single pulse.  e.g.  T 1 190 100
//  *   SWEEP <n>         ramp PWM upward - find the perception threshold
//  *   SL <n>            short, gap, long - can you tell them apart?
//  *   RAND <n>          20 blind short/long trials, scored
//  *   KICK <n>          same short pulse with and without kick-start
//  *   ALL <pwm>         all five at once - checks for supply brownout
//  *   STOP              everything off
//  *
//  * Fingers are numbered 1-5: thumb, index, middle, ring, pinky.
//  */

// const int   MOTOR_PIN[5]  = {3, 5, 6, 9, 10};
// const char* FINGER[5]     = {"thumb", "index", "middle", "ring", "pinky"};

// // Timings - keep these in sync with haptic_engine.ino
// int SHORT_MS = 100;
// int LONG_MS  = 300;
// int GAP_MS   = 120;

// // Intensity
// int INT_NEUTRAL = 190;   // ~3.0 V through the ULN2003
// int KICK_PWM    = 255;   // full power to break static friction
// int KICK_MS     = 25;    // how long the kick lasts

// unsigned long randSeedCounter = 0;

// // ---------------------------------------------------------------- primitives

// void allOff() {
//   for (int i = 0; i < 5; i++) analogWrite(MOTOR_PIN[i], 0);
// }

// // One pulse, with the kick-start that makes short pulses perceptible.
// void pulse(int idx, int pwm, int ms, bool kick = true) {
//   if (idx < 0 || idx > 4) return;
//   int pin = MOTOR_PIN[idx];

//   if (kick && ms > KICK_MS) {
//     analogWrite(pin, KICK_PWM);
//     delay(KICK_MS);
//     analogWrite(pin, pwm);
//     delay(ms - KICK_MS);
//   } else {
//     analogWrite(pin, kick ? KICK_PWM : pwm);
//     delay(ms);
//   }
//   analogWrite(pin, 0);
// }

// // ---------------------------------------------------------------- routines

// void cmdID() {
//   Serial.println(F("\n-- wiring check --"));
//   Serial.println(F("Each motor fires for 600 ms. Confirm the finger that buzzes"));
//   Serial.println(F("matches the name printed. Swapped tape = swapped wires.\n"));
//   for (int i = 0; i < 5; i++) {
//     Serial.print(F("  ")); Serial.print(i + 1);
//     Serial.print(F("  ")); Serial.print(FINGER[i]);
//     Serial.print(F("   (pin ")); Serial.print(MOTOR_PIN[i]); Serial.println(F(")"));
//     pulse(i, INT_NEUTRAL, 600);
//     delay(700);
//   }
//   Serial.println(F("-- done --\n"));
// }

// void cmdSweep(int idx) {
//   Serial.print(F("\n-- intensity sweep: ")); Serial.print(FINGER[idx]);
//   Serial.println(F(" --"));
//   Serial.println(F("Note the FIRST value you can clearly feel. That is your"));
//   Serial.println(F("floor for this finger once taped.\n"));

//   for (int pwm = 60; pwm <= 255; pwm += 15) {
//     Serial.print(F("  pwm ")); Serial.print(pwm);
//     Serial.print(F("   ~")); Serial.print(pwm * 4.0 / 255.0, 1);
//     Serial.println(F(" V"));
//     pulse(idx, pwm, 400, false);      // no kick - we want the true threshold
//     delay(900);
//   }
//   Serial.println(F("-- done --\n"));
// }

// void cmdSL(int idx) {
//   Serial.print(F("\n-- short vs long: ")); Serial.print(FINGER[idx]);
//   Serial.println(F(" --"));
//   Serial.print(F("SHORT (")); Serial.print(SHORT_MS); Serial.println(F(" ms)"));
//   pulse(idx, INT_NEUTRAL, SHORT_MS);
//   delay(1200);
//   Serial.print(F("LONG  (")); Serial.print(LONG_MS); Serial.println(F(" ms)"));
//   pulse(idx, INT_NEUTRAL, LONG_MS);
//   Serial.println(F("\nIf those feel the same, raise LONG_MS or lower SHORT_MS.\n"));
// }

// void cmdRand(int idx) {
//   Serial.print(F("\n-- blind discrimination test: ")); Serial.print(FINGER[idx]);
//   Serial.println(F(" --"));
//   Serial.println(F("20 pulses, random short or long. Look away from the screen."));
//   Serial.println(F("Write down S or L for each. Answers print at the end.\n"));
//   delay(3000);

//   randomSeed(millis() + randSeedCounter++);
//   char answers[20];

//   for (int i = 0; i < 20; i++) {
//     bool isLong = random(2);
//     answers[i] = isLong ? 'L' : 'S';
//     Serial.print(F("  trial ")); Serial.println(i + 1);
//     pulse(idx, INT_NEUTRAL, isLong ? LONG_MS : SHORT_MS);
//     delay(1600);
//   }

//   Serial.print(F("\nanswers: "));
//   for (int i = 0; i < 20; i++) {
//     Serial.print(answers[i]);
//     Serial.print(' ');
//   }
//   Serial.println(F("\n\nScore yourself. Below 18/20 and the timings need work."));
//   Serial.println(F("This number is worth putting in your README.\n"));
// }

// void cmdKick(int idx) {
//   Serial.print(F("\n-- kick-start comparison: ")); Serial.print(FINGER[idx]);
//   Serial.println(F(" --"));
//   Serial.println(F("WITHOUT kick (motor may barely spin up):"));
//   pulse(idx, INT_NEUTRAL, SHORT_MS, false);
//   delay(1500);
//   Serial.println(F("WITH kick:"));
//   pulse(idx, INT_NEUTRAL, SHORT_MS, true);
//   Serial.println(F("\nThe second should feel noticeably sharper.\n"));
// }

// void cmdAll(int pwm) {
//   Serial.println(F("\n-- all five at once --"));
//   Serial.println(F("Watch for the board browning out or resetting."));
//   Serial.println(F("If it does, the motor supply cannot handle 5 simultaneous starts.\n"));
//   for (int i = 0; i < 5; i++) analogWrite(MOTOR_PIN[i], KICK_PWM);
//   delay(KICK_MS);
//   for (int i = 0; i < 5; i++) analogWrite(MOTOR_PIN[i], pwm);
//   delay(800);
//   allOff();
//   Serial.println(F("-- done --\n"));
// }

// void cmdHelp() {
//   Serial.println(F("\nHapticTalk motor calibration"));
//   Serial.println(F("  ID                 wiring check, all five in order"));
//   Serial.println(F("  T <n> <pwm> <ms>   single pulse"));
//   Serial.println(F("  SWEEP <n>          find the perception threshold"));
//   Serial.println(F("  SL <n>             short vs long comparison"));
//   Serial.println(F("  RAND <n>           20 blind trials, scored"));
//   Serial.println(F("  KICK <n>           kick-start on vs off"));
//   Serial.println(F("  ALL <pwm>          all five - brownout check"));
//   Serial.println(F("  STOP               everything off"));
//   Serial.println(F("\n  n = 1 thumb, 2 index, 3 middle, 4 ring, 5 pinky\n"));
// }

// // ---------------------------------------------------------------- serial

// void setup() {
//   Serial.begin(9600);
//   for (int i = 0; i < 5; i++) {
//     pinMode(MOTOR_PIN[i], OUTPUT);
//     analogWrite(MOTOR_PIN[i], 0);
//   }
//   delay(500);
//   Serial.println(F("\n=== HapticTalk motor calibration ==="));
//   cmdHelp();
//   Serial.println(F("Suggested order: ID -> SWEEP each -> KICK -> SL -> RAND\n"));
// }

// void loop() {
//   if (!Serial.available()) return;

//   String line = Serial.readStringUntil('\n');
//   line.trim();
//   line.toUpperCase();
//   if (line.length() == 0) return;

//   int sp1 = line.indexOf(' ');
//   String cmd = (sp1 < 0) ? line : line.substring(0, sp1);
//   String rest = (sp1 < 0) ? "" : line.substring(sp1 + 1);
//   rest.trim();

//   if (cmd == "HELP") { cmdHelp(); return; }
//   if (cmd == "STOP") { allOff(); Serial.println(F("all off")); return; }
//   if (cmd == "ID")   { cmdID(); return; }

//   if (cmd == "ALL") {
//     int pwm = rest.length() ? rest.toInt() : INT_NEUTRAL;
//     cmdAll(constrain(pwm, 0, 255));
//     return;
//   }

//   // Everything below needs a finger number
//   int n = rest.toInt();
//   if (n < 1 || n > 5) {
//     Serial.println(F("finger must be 1-5 (thumb..pinky)"));
//     return;
//   }
//   int idx = n - 1;

//   if (cmd == "SWEEP") { cmdSweep(idx); return; }
//   if (cmd == "SL")    { cmdSL(idx);    return; }
//   if (cmd == "RAND")  { cmdRand(idx);  return; }
//   if (cmd == "KICK")  { cmdKick(idx);  return; }

//   if (cmd == "T") {
//     int sp2 = rest.indexOf(' ');
//     if (sp2 < 0) { Serial.println(F("usage: T <n> <pwm> <ms>")); return; }
//     String tail = rest.substring(sp2 + 1);
//     tail.trim();
//     int sp3 = tail.indexOf(' ');
//     int pwm = (sp3 < 0) ? tail.toInt() : tail.substring(0, sp3).toInt();
//     int ms  = (sp3 < 0) ? SHORT_MS     : tail.substring(sp3 + 1).toInt();
//     pwm = constrain(pwm, 0, 255);
//     ms  = constrain(ms, 10, 3000);
//     Serial.print(F("pulse ")); Serial.print(FINGER[idx]);
//     Serial.print(F(" pwm ")); Serial.print(pwm);
//     Serial.print(F(" for ")); Serial.print(ms); Serial.println(F(" ms"));
//     pulse(idx, pwm, ms);
//     return;
//   }

//   Serial.print(F("unknown command: "));
//   Serial.println(cmd);
// }