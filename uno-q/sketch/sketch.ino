
/*
  Still Loading... — Arduino UNO Q light sketch

  State codes:
    0 = idle
    1 = running
    2 = slow
    3 = suspected_stall
    4 = failed
    5 = completed

  RGB LED 3 indicates state color.
  The blue 8x13 matrix shows a distinct state pattern.
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
  frame[row * COLS + col] = brightness;
}

void show_frame() {
  matrix.draw(frame);
}

void set_job_lights(int state_code, int progress) {
  if (state_code < 0 || state_code > 5) state_code = 0;
  if (progress < 0) progress = 0;
  if (progress > 100) progress = 100;

  current_state = state_code;
  current_progress = progress;
}

void paint_led3(int red, int green, int blue) {
  analogWrite(LED3_R, red);
  analogWrite(LED3_G, green);
  analogWrite(LED3_B, blue);
}

void draw_progress_bar(int row, int brightness) {
  int lit = (current_progress * COLS) / 100;

  // Show at least one pixel while running.
  if (lit < 1) lit = 1;

  for (int col = 0; col < lit; col++) {
    pixel(row, col, brightness);
  }
}

void draw_idle_dots(unsigned long ms) {
  const int cols[3] = {3, 6, 9};
  int active = (ms / 350) % 3;

  for (int i = 0; i < 3; i++) {
    pixel(3, cols[i], i == active ? 7 : 1);
  }
}

void draw_slow_pattern(unsigned long ms) {
  // Amber RGB plus a pair of alternating matrix bars.
  int width = 2 + ((ms / 450) % 4);

  for (int col = 0; col < width; col++) {
    pixel(2, col, 5);
    pixel(5, col, 5);
  }
}

void draw_warning() {
  // Large exclamation mark: suspected stall.
  pixel(1, 6, 7);
  pixel(2, 6, 7);
  pixel(3, 6, 7);
  pixel(4, 6, 7);
  pixel(6, 6, 7);
}

void draw_x() {
  for (int i = 0; i < 5; i++) {
    pixel(i + 1, 4 + i, 7);
    pixel(i + 1, 8 - i, 7);
  }
}

void draw_check() {
  pixel(4, 3, 7);
  pixel(5, 4, 7);
  pixel(4, 5, 7);
  pixel(3, 6, 7);
  pixel(2, 7, 7);
  pixel(1, 8, 7);
}

void render(unsigned long ms) {
  clear_frame();
  int state = current_state;

  if (state == 0) {
    // IDLE: moving three dots, dim neutral RGB.
    paint_led3(6, 6, 10);
    draw_idle_dots(ms);

  } else if (state == 1) {
    // RUNNING: blue RGB and a progress bar.
    int phase = (ms / 50) % 80;
    int level = phase < 40 ? phase : 80 - phase;
    paint_led3(0, 0, level * 2);
    draw_progress_bar(6, 5);

  } else if (state == 2) {
    // SLOW: amber RGB and two moving bars.
    paint_led3(90, 35, 0);
    draw_slow_pattern(ms);

  } else if (state == 3) {
    // SUSPECTED STALL: blinking red/purple RGB and an exclamation mark.
    bool on = ((ms / 250) % 2) == 0;
    paint_led3(on ? 90 : 0, 0, on ? 45 : 0);
    draw_warning();

  } else if (state == 4) {
    // FAILED: steady red RGB and an X.
    paint_led3(100, 0, 0);
    draw_x();

  } else if (state == 5) {
    // COMPLETED: green RGB and a checkmark.
    paint_led3(0, 100, 0);
    draw_check();
  }

  show_frame();
}

void setup() {
  pinMode(LED3_R, OUTPUT);
  pinMode(LED3_G, OUTPUT);
  pinMode(LED3_B, OUTPUT);

  matrix.begin();
  matrix.setGrayscaleBits(3);

  Bridge.begin();
  Bridge.provide("set_job_lights", set_job_lights);

  render(0);
}

void loop() {
  render(millis());
  delay(30);
}
