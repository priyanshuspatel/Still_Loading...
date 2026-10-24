/*
  Still Loading... light sketch for the Arduino UNO Q.

  Paste this into the Sketch tab of an Arduino App Lab app.
  The Linux receiver keeps listening on port 8090. This sketch only
  draws. It reads a state code from Bridge and animates with millis(),
  so the network receiver does not sleep.

  State codes, matching shared/state_engine.py:
    0 idle
    1 running
    2 slow
    3 suspected_stall
    4 failed
    5 completed

  LED 3 is the PWM RGB LED on the microcontroller (official example:
  Bridge.provide("set_led3_color")). The 8x13 matrix is blue only, so
  red, amber, and green are shown on LED 3. The matrix shows a shape.

  Libraries used, both shipped for the UNO Q:
    Arduino_RouterBridge.h
    Arduino_LED_Matrix.h
*/

#include <Arduino_RouterBridge.h>
#include "Arduino_LED_Matrix.h"

Arduino_LED_Matrix matrix;

const int ROWS = 8;
const int COLS = 13;
uint8_t frame[ROWS * COLS];

volatile int current_state = 0;
volatile int current_progress = 0;

void clear_frame() {
  memset(frame, 0, sizeof(frame));
}

void pixel(int row, int col, uint8_t brightness) {
  if (row < 0 || row >= ROWS || col < 0 || col >= COLS) {
    return;
  }
  frame[(row * COLS) + col] = brightness;
}

void show_frame() {
  matrix.draw(frame);
}

// Same signature style as the official set_led3_color(int, int, int) provider.
void set_job_lights(int state_code, int progress) {
  if (state_code < 0) {
    state_code = 0;
  }
  if (state_code > 5) {
    state_code = 0;
  }
  if (progress < 0) {
    progress = 0;
  }
  if (progress > 100) {
    progress = 100;
  }
  current_state = state_code;
  current_progress = progress;
}

void paint_led3(int red, int green, int blue) {
  // The official Color Your LEDs example writes these PWM values directly.
  analogWrite(LED3_R, red);
  analogWrite(LED3_G, green);
  analogWrite(LED3_B, blue);
}

void draw_progress_bar(int row, int brightness) {
  int lit = (current_progress * COLS) / 100;
  if (lit < 1 && current_state == 1) {
    lit = 1;
  }
  for (int col = 0; col < lit; col++) {
    pixel(row, col, brightness);
  }
}

void draw_three_dots(int brightness, int highlight) {
  const int cols[3] = {3, 6, 9};
  for (int index = 0; index < 3; index++) {
    uint8_t value = index == highlight ? brightness : 1;
    pixel(3, cols[index], value);
  }
}

void draw_x() {
  for (int step = 0; step < 5; step++) {
    pixel(1 + step, 4 + step, 5);
    pixel(1 + step, 8 - step, 5);
  }
}

void draw_check() {
  pixel(4, 4, 5);
  pixel(5, 5, 5);
  pixel(4, 6, 5);
  pixel(3, 7, 5);
  pixel(2, 8, 5);
}

void render(unsigned long ms) {
  clear_frame();
  int state = current_state;

  if (state == 1) {
    // Calm blue pulse, kept dim on purpose.
    int phase = (ms / 50) % 80;
    int level = phase < 40 ? phase : 80 - phase;
    paint_led3(0, 0, level);
    draw_progress_bar(6, 3);
  } else if (state == 2) {
    paint_led3(90, 35, 0);
    draw_progress_bar(3, 4);
  } else if (state == 3) {
    // Two short blinks, then a pause. Different from the slow amber hold.
    int phase = (ms / 140) % 8;
    bool on = phase == 0 || phase == 2;
    paint_led3(on ? 70 : 0, 0, on ? 50 : 0);
    draw_three_dots(on ? 5 : 1, (ms / 400) % 3);
  } else if (state == 4) {
    paint_led3(90, 0, 0);
    draw_x();
  } else if (state == 5) {
    paint_led3(0, 70, 0);
    draw_check();
  } else {
    // State 0, idle. The moving dots are this idle pattern.
    // They stay until set_job_lights receives another code.
    paint_led3(6, 6, 10);
    draw_three_dots(2, (ms / 700) % 3);
  }

  show_frame();
}

void setup() {
  pinMode(LED3_R, OUTPUT);
  pinMode(LED3_G, OUTPUT);
  pinMode(LED3_B, OUTPUT);

  matrix.begin();
  // 3-bit grayscale is the setting used by the official matrix examples.
  // Pixel values in this sketch stay in the range 0 to 7.
  matrix.setGrayscaleBits(3);

  Bridge.begin();
  Bridge.provide("set_job_lights", set_job_lights);
  render(0);
}

void loop() {
  render(millis());
  delay(30);
}
